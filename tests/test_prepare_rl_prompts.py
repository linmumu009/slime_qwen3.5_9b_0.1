import json

from scripts.prepare_rl_prompts import convert_record, deduplicate_prompts, stable_json


def trajectory(answer: str, source_suffix: str = "") -> dict:
    return {
        "messages": [
            {"role": "system", "content": "Use tools carefully.", "loss": 0},
            {"role": "user", "content": "Find the result.", "loss": 1},
            {"role": "assistant", "content": answer, "loss": 1},
            {"role": "tool_call", "content": f"call-{source_suffix}"},
            {"role": "tool_response", "content": f"response-{source_suffix}"},
        ],
        "tools": json.dumps([{"type": "function", "function": {"name": "lookup"}}]),
    }


def test_convert_record_keeps_only_prompt_and_tool_schema() -> None:
    environment = {"environment_id": "sft/example", "task_id": "task-7"}
    record = convert_record(trajectory("private reference answer"), 7, "sample", "seed", environment)

    assert record.payload["prompt"] == [
        {"role": "system", "content": "Use tools carefully."},
        {"role": "user", "content": "Find the result."},
    ]
    assert record.payload["tools"][0]["function"]["name"] == "lookup"
    assert record.payload["metadata"]["source_lines"] == [7]
    assert record.payload["metadata"]["environment"] == environment
    assert "private reference answer" not in stable_json(record.payload)
    assert "loss" not in stable_json(record.payload)


def test_deduplicate_prompts_collapses_answers_without_leaking_content() -> None:
    first = convert_record(trajectory("answer one", "a"), 1, "sample", "seed")
    second_item = trajectory("answer two", "b")
    second_item["messages"][3]["content"] = "call-a"
    second_item["messages"][4]["content"] = "response-a"
    second = convert_record(second_item, 2, "sample", "seed")

    deduplicated = deduplicate_prompts([first, second])

    assert len(deduplicated) == 1
    metadata = deduplicated[0].payload["metadata"]
    assert metadata["source_lines"] == [1, 2]
    assert metadata["reference_trajectory_count"] == 2
    assert len(metadata["reference_trajectory_sha256"]) == 2
    rendered = stable_json(deduplicated[0].payload)
    assert "answer one" not in rendered
    assert "answer two" not in rendered
