#!/usr/bin/env python3
"""Run one offline SGLang generation without using the HTTP server."""

from __future__ import annotations

import argparse
import json

import sglang as sgl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--tp-size", type=int, default=2)
    parser.add_argument("--context-length", type=int, default=4096)
    parser.add_argument("--mem-fraction-static", type=float, default=0.7)
    parser.add_argument("--prompt", default="用一句话回答：1+1等于几？")
    parser.add_argument("--max-new-tokens", type=int, default=16)
    args = parser.parse_args()

    engine = None
    try:
        engine = sgl.Engine(
            model_path=args.model_path,
            device="npu",
            tp_size=args.tp_size,
            attention_backend="ascend",
            sampling_backend="ascend",
            mm_attention_backend="ascend_attn",
            enable_multimodal=True,
            trust_remote_code=True,
            context_length=args.context_length,
            mem_fraction_static=args.mem_fraction_static,
            disable_radix_cache=True,
            disable_cuda_graph=True,
            disable_overlap_schedule=True,
        )
        output = engine.generate(
            args.prompt,
            {"temperature": 0, "max_new_tokens": args.max_new_tokens},
        )
        print(json.dumps({"prompt": args.prompt, "output": output}, ensure_ascii=False))
        return 0
    finally:
        if engine is not None:
            engine.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
