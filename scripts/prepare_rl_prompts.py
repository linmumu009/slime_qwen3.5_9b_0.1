#!/usr/bin/env python3
"""Convert completed tool trajectories into prompt-only datasets for online RL."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROMPT_ROLES = {"system", "developer", "user"}


@dataclass(frozen=True)
class ConvertedRecord:
    source_line: int
    group_hash: str
    split_key: str
    payload: dict[str, Any]


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def clean_prompt_message(message: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in message.items() if key != "loss"}
    if "role" not in cleaned or "content" not in cleaned:
        raise ValueError("prompt message must contain role and content")
    return cleaned


def convert_record(
    item: dict[str, Any],
    source_line: int,
    source_name: str,
    seed: str,
    environment: dict[str, Any] | None = None,
) -> ConvertedRecord:
    messages = item.get("messages")
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    prompt: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("every message must be an object")
        role = message.get("role")
        if role not in PROMPT_ROLES:
            break
        prompt.append(clean_prompt_message(message))

    if not prompt or not any(message.get("role") == "user" for message in prompt):
        raise ValueError("trajectory does not start with a usable user prompt")

    tools = item.get("tools", [])
    if isinstance(tools, str):
        tools = json.loads(tools)
    if not isinstance(tools, list):
        raise ValueError("tools must decode to a list")

    prompt_hash = sha256_json(prompt)
    prompt_tools_hash = sha256_json({"prompt": prompt, "tools": tools})
    trajectory_hash = sha256_json(messages)
    environment_id = environment.get("environment_id") if environment else None
    group_hash = sha256_json(
        {"prompt": prompt, "tools": tools, "environment_id": environment_id}
    )
    split_key = hashlib.sha256(f"{seed}:{group_hash}".encode("utf-8")).hexdigest()
    metadata = {
        "source_name": source_name,
        "prompt_sha256": prompt_hash,
        "prompt_tools_sha256": prompt_tools_hash,
        "sample_group_sha256": group_hash,
        "source_lines": [source_line],
        "reference_trajectory_sha256": [trajectory_hash],
        "reference_message_counts": [len(messages)],
    }
    if environment is not None:
        metadata["environment"] = environment

    payload = {
        "prompt": prompt,
        "tools": tools,
        "metadata": metadata,
    }
    return ConvertedRecord(
        source_line=source_line,
        group_hash=group_hash,
        split_key=split_key,
        payload=payload,
    )


def deduplicate_prompts(records: list[ConvertedRecord]) -> list[ConvertedRecord]:
    unique: dict[str, ConvertedRecord] = {}
    for record in records:
        existing = unique.get(record.group_hash)
        if existing is None:
            unique[record.group_hash] = record
            continue

        metadata = existing.payload["metadata"]
        incoming = record.payload["metadata"]
        metadata["source_lines"].extend(incoming["source_lines"])
        metadata["reference_trajectory_sha256"].extend(incoming["reference_trajectory_sha256"])
        metadata["reference_message_counts"].extend(incoming["reference_message_counts"])

    for record in unique.values():
        record.payload["metadata"]["reference_trajectory_count"] = len(
            record.payload["metadata"]["reference_trajectory_sha256"]
        )
    return list(unique.values())


def write_jsonl(path: Path, records: list[ConvertedRecord]) -> str:
    digest = hashlib.sha256()
    with path.open("wb") as handle:
        for record in sorted(records, key=lambda value: value.source_line):
            raw = (stable_json(record.payload) + "\n").encode("utf-8")
            handle.write(raw)
            digest.update(raw)
    return digest.hexdigest()


def load_environment_manifest(path: Path) -> dict[int, dict[str, Any]]:
    mapping: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for manifest_line, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            combined_line = int(row.pop("combined_line"))
            if combined_line in mapping:
                raise ValueError(f"duplicate combined_line in environment manifest: {combined_line}")
            mapping[combined_line] = row
    if not mapping:
        raise ValueError("environment manifest is empty")
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Completed trajectory JSONL")
    parser.add_argument("output_dir", type=Path, help="Directory for prompt datasets and manifest")
    parser.add_argument("--source-name", default="upstream_correct_screen_v1")
    parser.add_argument("--eval-fraction", type=float, default=0.10)
    parser.add_argument("--seed", default="20260716")
    parser.add_argument(
        "--environment-manifest",
        type=Path,
        help="Optional JSONL keyed by combined_line; values are copied into metadata.environment",
    )
    args = parser.parse_args()

    if not 0.0 < args.eval_fraction < 1.0:
        parser.error("--eval-fraction must be between 0 and 1")

    source = args.input.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    environment_mapping = (
        load_environment_manifest(args.environment_manifest.resolve()) if args.environment_manifest else None
    )

    converted: list[ConvertedRecord] = []
    rejected: list[dict[str, Any]] = []
    input_digest = hashlib.sha256()

    with source.open("rb") as handle:
        for source_line, raw_line in enumerate(handle, start=1):
            input_digest.update(raw_line)
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line.decode("utf-8"))
                if not isinstance(item, dict):
                    raise ValueError("record must be an object")
                environment = environment_mapping.get(source_line) if environment_mapping else None
                if environment_mapping is not None and environment is None:
                    raise ValueError(f"environment manifest has no row for source line {source_line}")
                converted.append(convert_record(item, source_line, args.source_name, args.seed, environment))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                rejected.append({"source_line": source_line, "reason": str(error)})

    if not converted:
        raise RuntimeError("no records were converted")

    unique_prompts = deduplicate_prompts(converted)
    eval_count = max(1, round(len(unique_prompts) * args.eval_fraction))
    ranked = sorted(unique_prompts, key=lambda record: record.split_key)
    eval_lines = {record.source_line for record in ranked[:eval_count]}
    eval_records = [record for record in unique_prompts if record.source_line in eval_lines]
    train_records = [record for record in unique_prompts if record.source_line not in eval_lines]

    train_path = output_dir / "train_prompts.jsonl"
    eval_path = output_dir / "eval_prompts.jsonl"
    rejected_path = output_dir / "rejected_records.json"
    manifest_path = output_dir / "manifest.json"

    train_sha256 = write_jsonl(train_path, train_records)
    eval_sha256 = write_jsonl(eval_path, eval_records)
    rejected_path.write_text(json.dumps(rejected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    unique_prompt_tool_groups = len(
        {record.payload["metadata"]["prompt_tools_sha256"] for record in converted}
    )
    manifest = {
        "input": str(source),
        "input_sha256": input_digest.hexdigest(),
        "source_name": args.source_name,
        "seed": args.seed,
        "eval_fraction": args.eval_fraction,
        "converted_records": len(converted),
        "unique_prompt_tool_groups": unique_prompt_tool_groups,
        "unique_sample_groups": len(unique_prompts),
        "cross_environment_prompt_collisions": len(unique_prompts) - unique_prompt_tool_groups,
        "collapsed_duplicate_trajectories": len(converted) - len(unique_prompts),
        "rejected_records": len(rejected),
        "environment_manifest": str(args.environment_manifest.resolve()) if args.environment_manifest else None,
        "environment_records": len(environment_mapping) if environment_mapping else 0,
        "train": {"path": str(train_path), "records": len(train_records), "sha256": train_sha256},
        "eval": {"path": str(eval_path), "records": len(eval_records), "sha256": eval_sha256},
        "rejected": {"path": str(rejected_path)},
        "contract": {
            "input_key": "prompt",
            "tool_key": "tools",
            "metadata_key": "metadata",
            "apply_chat_template": True,
            "contains_reference_trajectory_content": False,
            "sample_groups_are_disjoint": True,
            "intended_use": "online_rl_prompt_source",
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
