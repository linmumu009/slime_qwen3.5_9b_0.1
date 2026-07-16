#!/usr/bin/env python3
"""Run a small allocation and matrix multiplication on every visible Ascend NPU."""

from __future__ import annotations

import argparse
import json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-size", type=int, default=256)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.matrix_size <= 0:
        raise ValueError("--matrix-size must be positive")

    import torch
    import torch_npu  # noqa: F401  # registers the NPU backend

    device_count = torch.npu.device_count()
    results: list[dict[str, object]] = []
    for index in range(device_count):
        device = torch.device(f"npu:{index}")
        left = torch.ones((args.matrix_size, args.matrix_size), device=device)
        right = torch.full_like(left, 2.0)
        product = left @ right
        torch.npu.synchronize(index)
        expected = 2.0 * args.matrix_size
        observed = float(product[0, 0].cpu())
        results.append(
            {
                "device": index,
                "name": torch.npu.get_device_name(index),
                "observed": observed,
                "expected": expected,
                "ok": observed == expected,
            }
        )

    report = {
        "torch": torch.__version__,
        "torch_npu": torch_npu.__version__,
        "device_count": device_count,
        "all_ok": device_count > 0 and all(item["ok"] for item in results),
        "devices": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
