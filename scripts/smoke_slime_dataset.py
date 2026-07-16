#!/usr/bin/env python3
"""Load prompt/tool JSONL through slime's real Dataset and Qwen chat template."""

from __future__ import annotations

import argparse
import json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("model")
    parser.add_argument("--records", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=32768)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.records <= 0:
        raise ValueError("--records must be positive")

    from transformers import AutoTokenizer

    from slime.utils.data import Dataset

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    sliced_path = f"{args.dataset}@[0:{args.records}]"
    dataset = Dataset(
        sliced_path,
        tokenizer,
        processor=None,
        max_length=args.max_length,
        prompt_key="prompt",
        tool_key="tools",
        metadata_key="metadata",
        apply_chat_template=True,
    )

    samples = []
    for sample in dataset.origin_samples:
        token_count = len(tokenizer(sample.prompt, add_special_tokens=False)["input_ids"])
        tools = sample.metadata.get("tools")
        samples.append(
            {
                "prompt_is_string": isinstance(sample.prompt, str),
                "prompt_chars": len(sample.prompt),
                "prompt_tokens": token_count,
                "tool_count": len(tools) if isinstance(tools, list) else None,
                "has_prompt_hash": "prompt_sha256" in sample.metadata,
            }
        )

    report = {
        "requested_records": args.records,
        "loaded_records": len(samples),
        "all_prompts_rendered": bool(samples) and all(item["prompt_is_string"] for item in samples),
        "all_tools_loaded": bool(samples) and all((item["tool_count"] or 0) > 0 for item in samples),
        "samples": samples,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_prompts_rendered"] and report["all_tools_loaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
