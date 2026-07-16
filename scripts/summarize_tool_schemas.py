#!/usr/bin/env python3
"""Summarize tool names and schema frequencies in trajectory JSONL without message content."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    records = 0
    malformed_tools = 0
    tool_names: Counter[str] = Counter()
    tool_sets: Counter[str] = Counter()
    schema_hashes: Counter[str] = Counter()
    required_fields: dict[str, Counter[str]] = {}

    with args.input.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            records += 1
            tools = item.get("tools", [])
            if isinstance(tools, str):
                tools = json.loads(tools)
            if not isinstance(tools, list):
                malformed_tools += 1
                continue

            names: list[str] = []
            for tool in tools:
                if not isinstance(tool, dict):
                    malformed_tools += 1
                    continue
                function = tool.get("function") or {}
                name = str(function.get("name", "<missing>"))
                names.append(name)
                tool_names[name] += 1
                digest = hashlib.sha256(stable_json(tool).encode("utf-8")).hexdigest()
                schema_hashes[f"{name}:{digest}"] += 1
                parameters = function.get("parameters") or {}
                required = parameters.get("required") or []
                counter = required_fields.setdefault(name, Counter())
                for field in required:
                    counter[str(field)] += 1
            tool_sets[",".join(sorted(names))] += 1

    report = {
        "records": records,
        "malformed_tools": malformed_tools,
        "tool_names": dict(tool_names.most_common()),
        "tool_sets": dict(tool_sets.most_common()),
        "distinct_schema_count_by_tool": {
            name: sum(1 for key in schema_hashes if key.startswith(f"{name}:")) for name in tool_names
        },
        "required_fields": {
            name: dict(counter.most_common()) for name, counter in sorted(required_fields.items())
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if malformed_tools == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
