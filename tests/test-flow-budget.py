#!/usr/bin/env python3
"""预算监控最小测试：真实 token 记录必须触发 WARN/STOP 与接力提示。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "flow-budget.py"
spec = importlib.util.spec_from_file_location("flow_budget", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_session(path: Path, input_tokens: int, cached: int, window: int, turns: int) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index in range(turns):
            handle.write(
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "task_started",
                            "turn_id": f"turn-{index}",
                            "model_context_window": window,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        handle.write(
            json.dumps(
                {
                    "type": "token_usage_record",
                    "payload": {
                        "turn_token_usage": {
                            "input_tokens": input_tokens,
                            "cached_input_tokens": cached,
                            "output_tokens": 100,
                            "total_tokens": input_tokens + 100,
                        },
                        "thread_token_usage": {
                            "input_tokens": input_tokens * turns,
                            "cached_input_tokens": cached * turns,
                        },
                    },
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {"type": "function_call", "name": "exec_command"},
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        normal = root / "normal.jsonl"
        warning = root / "warning.jsonl"
        stopped = root / "stopped.jsonl"
        write_session(normal, 40_000, 30_000, 100_000, 3)
        write_session(warning, 75_000, 40_000, 100_000, 21)
        write_session(stopped, 90_000, 0, 100_000, 25)

        normal_report = module.summarize(normal)
        warning_report = module.summarize(warning)
        stopped_report = module.summarize(stopped)

        assert normal_report["level"] == "OK", normal_report
        assert warning_report["level"] == "WARN", warning_report
        assert stopped_report["level"] == "STOP", stopped_report
        prompt = module.handoff_prompt("继续组件库", stopped_report)
        assert "--intent" in prompt, prompt
        assert "预算熔断" in prompt, prompt
        assert "不要复读历史聊天" in prompt, prompt
    print("PASS: flow-budget classifies OK/WARN/STOP and emits a handoff prompt")


if __name__ == "__main__":
    main()
