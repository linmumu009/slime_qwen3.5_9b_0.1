#!/usr/bin/env python3
"""Reconstruct combined trajectory line to sandbox environment metadata from a dataset plan."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def output_group(row: dict[str, Any]) -> str:
    phase = row["phase"]
    if phase == "long_32k_review":
        return "long_32k_review"
    if row["split"] != "train":
        return "heldout"
    if row["quality_tier"] == "sql_result_verified":
        return "train_strong_verified"
    return "train_review"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sandbox-root", type=Path)
    parser.add_argument("--sandbox-split", default="sft")
    parser.add_argument(
        "--required-asset",
        action="append",
        default=[],
        help="Relative path that must exist in every referenced environment; repeatable",
    )
    args = parser.parse_args()

    by_source: dict[str, list[dict[str, Any]]] = {}
    with args.plan.open(encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            by_source.setdefault(row["source_file"], []).append(row)

    grouped: dict[str, list[dict[str, Any]]] = {
        "train_strong_verified": [],
        "train_review": [],
    }
    for rows in by_source.values():
        for row in sorted(rows, key=lambda item: int(item["source_line"])):
            group = output_group(row)
            if group in grouped:
                grouped[group].append(row)

    ordered = grouped["train_strong_verified"] + grouped["train_review"]
    missing_environments: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    for combined_line, row in enumerate(ordered, start=1):
        environment_id = f"{args.sandbox_split}/{row['version']}"
        if args.sandbox_root:
            environment_path = args.sandbox_root / environment_id
            if not environment_path.is_dir():
                missing_environments[environment_id] += 1
            else:
                for asset in args.required_asset:
                    if not (environment_path / asset).exists():
                        missing_environments[f"{environment_id}/{asset}"] += 1
        output_rows.append(
            {
                "combined_line": combined_line,
                "environment_id": environment_id,
                "source_file": row["source_file"],
                "source_line": int(row["source_line"]),
                "version": row["version"],
                "task_id": row["task_id"],
                "task_type": row["type"],
                "quality_tier": row["quality_tier"],
                "dataset_group": output_group(row),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "records": len(output_rows),
        "groups": {name: len(rows) for name, rows in grouped.items()},
        "distinct_environments": len({row["environment_id"] for row in output_rows}),
        "required_assets": args.required_asset,
        "missing_environments": dict(missing_environments),
        "output": str(args.output.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not missing_environments else 1


if __name__ == "__main__":
    raise SystemExit(main())
