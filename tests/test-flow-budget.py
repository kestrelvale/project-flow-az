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
        # 窗口按真实值 950k；阈值按实测标定：首个「用户消息回放块」出现在
        # 单次输入 556166（P4 会话），所以 STOP 必须明显早于压缩区。
        write_session(normal, 40_000, 30_000, 950_000, 3)
        write_session(warning, 190_000, 40_000, 950_000, 12)
        write_session(stopped, 300_000, 0, 950_000, 23)

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
        # 交接必须是 SDD 蒸馏产物：规格点 + 待办，且禁止原样照抄用户消息。
        assert "SPE-1" in prompt and "规格点" in prompt, prompt
        assert "禁止" in prompt and "原样" in prompt, prompt

        # 标定锁：STOP 必须早于实测压缩区（556166），否则熔断永远晚于压缩。
        compaction_zone = 556_166
        assert module.STOP_INPUT_TOKENS < compaction_zone, module.STOP_INPUT_TOKENS
        assert module.WARN_INPUT_TOKENS < module.STOP_INPUT_TOKENS, module.WARN_INPUT_TOKENS
        assert module.STOP_RATIO * 950_000 < compaction_zone, module.STOP_RATIO

        # STOP 必须落盘回执：否则下一轮开工判定不了“熔断到底交接了没有”。
        project = root / "proj"
        (project / "flow").mkdir(parents=True)
        (project / "flow" / "进展.md").write_text(
            "## 2026-09-21 · 旧交接棒 · 总控\n- 现状: x\n", encoding="utf-8"
        )
        receipt = module.persist_stop(project, "tid-1", stopped_report, prompt)
        assert receipt is not None and receipt.is_file(), receipt
        data = json.loads(receipt.read_text(encoding="utf-8"))
        assert data["operation"] == "budget_stop", data
        assert data["handoff_head"] == "## 2026-09-21 · 旧交接棒 · 总控", data
        assert data["tool_calls"] == stopped_report["tool_calls"], data
        assert "接力" in data["handoff_prompt"] or "--intent" in data["handoff_prompt"], data
    print("PASS: flow-budget classifies OK/WARN/STOP and emits a handoff prompt")


if __name__ == "__main__":
    main()
