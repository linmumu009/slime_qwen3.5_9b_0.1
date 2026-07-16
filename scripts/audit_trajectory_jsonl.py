#!/usr/bin/env python3
"""Audit trajectory JSONL structure without emitting message content."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def distribution(values: list[int]) -> dict[str, int | None]:
    return {
        "min": min(values) if values else None,
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
    }


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Trajectory JSONL file")
    parser.add_argument("--output", type=Path, help="Write the JSON report here")
    args = parser.parse_args()

    source = args.input.resolve()
    file_digest = hashlib.sha256()
    records = 0
    malformed = 0
    blank_lines = 0
    non_object_records = 0
    invalid_messages = 0
    records_without_assistant = 0
    empty_assistant_messages = 0
    assistant_messages_with_tool_calls = 0

    top_level_key_sets: Counter[str] = Counter()
    message_key_sets: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    role_sequences: Counter[str] = Counter()
    content_type_counts: Counter[str] = Counter()
    tools_type_counts: Counter[str] = Counter()
    parsed_tools_type_counts: Counter[str] = Counter()
    tool_string_parse_errors = 0

    message_counts: list[int] = []
    trajectory_char_counts: list[int] = []
    assistant_char_counts: list[int] = []
    record_hashes: Counter[str] = Counter()
    message_hashes: Counter[str] = Counter()

    with source.open("rb") as handle:
        for raw_line in handle:
            file_digest.update(raw_line)
            if not raw_line.strip():
                blank_lines += 1
                continue

            try:
                item = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                malformed += 1
                continue

            records += 1
            record_hashes[stable_hash(item)] += 1
            if not isinstance(item, dict):
                non_object_records += 1
                continue

            top_level_key_sets[",".join(sorted(item))] += 1
            messages = item.get("messages")
            if not isinstance(messages, list):
                invalid_messages += 1
                continue

            message_hashes[stable_hash(messages)] += 1
            message_counts.append(len(messages))
            roles: list[str] = []
            trajectory_chars = 0
            assistant_chars = 0
            assistant_count = 0

            for message in messages:
                if not isinstance(message, dict):
                    content_type_counts[f"message:{type(message).__name__}"] += 1
                    continue

                message_key_sets[",".join(sorted(message))] += 1
                role = str(message.get("role", "<missing>"))
                roles.append(role)
                role_counts[role] += 1

                content = message.get("content")
                content_type_counts[type(content).__name__] += 1
                if isinstance(content, str):
                    content_chars = len(content)
                else:
                    content_chars = len(json.dumps(content, ensure_ascii=False)) if content is not None else 0
                trajectory_chars += content_chars

                if role == "assistant":
                    assistant_count += 1
                    assistant_chars += content_chars
                    tool_calls = message.get("tool_calls")
                    if tool_calls:
                        assistant_messages_with_tool_calls += 1
                    if content_chars == 0 and not tool_calls:
                        empty_assistant_messages += 1

            if assistant_count == 0:
                records_without_assistant += 1
            role_sequences[">".join(roles)] += 1
            trajectory_char_counts.append(trajectory_chars)
            assistant_char_counts.append(assistant_chars)

            tools = item.get("tools")
            tools_type_counts[type(tools).__name__] += 1
            if isinstance(tools, str):
                try:
                    parsed_tools = json.loads(tools)
                    parsed_tools_type_counts[type(parsed_tools).__name__] += 1
                except json.JSONDecodeError:
                    tool_string_parse_errors += 1

    duplicate_records = sum(count - 1 for count in record_hashes.values() if count > 1)
    duplicate_message_sets = sum(count - 1 for count in message_hashes.values() if count > 1)

    warnings: list[str] = []
    if malformed:
        warnings.append(f"{malformed} malformed JSON or UTF-8 lines")
    if invalid_messages:
        warnings.append(f"{invalid_messages} records do not contain a messages list")
    if records_without_assistant:
        warnings.append(f"{records_without_assistant} records contain no assistant message")
    if tool_string_parse_errors:
        warnings.append(f"{tool_string_parse_errors} tools strings are not valid JSON")
    if tools_type_counts.get("str", 0):
        warnings.append("tools is stored as a string and should be parsed before slime ingestion")

    report = {
        "source": str(source),
        "bytes": source.stat().st_size,
        "sha256": file_digest.hexdigest(),
        "records": records,
        "blank_lines": blank_lines,
        "malformed_lines": malformed,
        "non_object_records": non_object_records,
        "invalid_messages": invalid_messages,
        "records_without_assistant": records_without_assistant,
        "message_count": distribution(message_counts),
        "trajectory_content_chars": distribution(trajectory_char_counts),
        "assistant_content_chars": distribution(assistant_char_counts),
        "role_counts": dict(role_counts.most_common()),
        "top_role_sequences": dict(role_sequences.most_common(20)),
        "top_level_key_sets": dict(top_level_key_sets.most_common()),
        "message_key_sets": dict(message_key_sets.most_common()),
        "content_type_counts": dict(content_type_counts.most_common()),
        "tools_type_counts": dict(tools_type_counts.most_common()),
        "parsed_tools_type_counts": dict(parsed_tools_type_counts.most_common()),
        "tool_string_parse_errors": tool_string_parse_errors,
        "empty_assistant_messages": empty_assistant_messages,
        "assistant_messages_with_tool_calls": assistant_messages_with_tool_calls,
        "duplicate_records": duplicate_records,
        "duplicate_message_sets": duplicate_message_sets,
        "warnings": warnings,
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
