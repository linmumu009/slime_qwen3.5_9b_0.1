#!/usr/bin/env python3
"""Probe an SGLang OpenAI-compatible endpoint without proxy handling."""

from __future__ import annotations

import argparse
import http.client
import json
import sys
from typing import Any


def request_json(
    host: str,
    port: int,
    method: str,
    path: str,
    *,
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    body = None
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
    finally:
        connection.close()

    text = raw.decode("utf-8", errors="replace")
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    return response.status, parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--api-key")
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="用一句话回答：1+1等于几？")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    model_status, model_info = request_json(
        args.host,
        args.port,
        "GET",
        "/v1/models",
        api_key=args.api_key,
        timeout=args.timeout,
    )
    print(json.dumps({"models_status": model_status, "models": model_info}, ensure_ascii=False))
    if model_status != 200:
        return 1

    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "stream": False,
    }
    generation_status, generation = request_json(
        args.host,
        args.port,
        "POST",
        "/v1/chat/completions",
        api_key=args.api_key,
        payload=payload,
        timeout=args.timeout,
    )
    print(
        json.dumps(
            {"generation_status": generation_status, "response": generation},
            ensure_ascii=False,
        )
    )
    return 0 if generation_status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
