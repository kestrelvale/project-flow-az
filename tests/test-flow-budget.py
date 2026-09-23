#!/usr/bin/env python3
"""预算监控最小测试：真实 token 记录必须触发 WARN/STOP 与接力提示。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys

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
        # 窗口按实测真值 950k（中继会话统一声明 0.95×1e6）。
        # 用户 2026-09-23 拍板 WARN 45% / STOP 50%（知情取舍，见 CHANGELOG 4.15.2）。
        write_session(normal, 40_000, 30_000, 950_000, 3)
        write_session(warning, 440_000, 40_000, 950_000, 12)
        write_session(stopped, 490_000, 0, 950_000, 23)

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

        # 标定锁（防止阈值再被拍回绝对值）：三条推导约束必须同时成立。
        model_failure = 556_166          # 实测：模型开始回放用户消息的单次输入
        per_turn_p90 = 125_246           # 实测：单轮上下文增量 p90
        assert module.STOP_RATIO < module.MODEL_FAILURE_RATIO, module.STOP_RATIO
        assert module.WARN_RATIO < module.STOP_RATIO, module.WARN_RATIO
        assert module.STOP_RATIO * 950_000 < model_failure, module.STOP_RATIO
        # 272k 模型（有效窗口 258400）必须仍留出 ≥ 1 个 p90 轮的余量。
        assert (1 - module.STOP_RATIO) * 258_400 >= per_turn_p90, module.STOP_RATIO

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

        # 中段复查（--guard）：长 turn 内周期性自检的唯一手段（AGENTS.md 不装 Hook）。
        # 超线必须非零；未超线必须零且明确提示复查节奏。
        script = ROOT / "scripts" / "flow-budget.py"
        sessions = root / "sessions"
        sessions.mkdir()
        (sessions / "rollout-x-thread-guard.jsonl").write_text(
            (stopped.read_text(encoding="utf-8"), ) [0], encoding="utf-8"
        )
        hot = subprocess.run(
            [sys.executable, str(script), "--thread-id", "thread-guard",
             "--guard", "--sessions-root", str(sessions), "--project", str(project)],
            text=True, capture_output=True,
        )
        assert hot.returncode == 1, (hot.returncode, hot.stdout, hot.stderr)
        assert "中段复查 [STOP]" in hot.stdout, hot.stdout
        assert "立即停止扩展实现" in hot.stdout, hot.stdout
        # 用户反馈「要求交接却没有交接提示词」：中段复查必须把可复制的提示词给全。
        assert "project-flow 接力提示词" in hot.stdout, hot.stdout
        assert "--intent" in hot.stdout, hot.stdout

        (sessions / "rollout-x-thread-guard.jsonl").write_text(
            normal.read_text(encoding="utf-8"), encoding="utf-8"
        )
        cool = subprocess.run(
            [sys.executable, str(script), "--thread-id", "thread-guard",
             "--guard", "--sessions-root", str(sessions), "--project", str(project)],
            text=True, capture_output=True,
        )
        assert cool.returncode == 0, (cool.returncode, cool.stdout, cool.stderr)
        assert "每 50 次工具调用" in cool.stdout, cool.stdout

        # --print-relay：按需取回交接提示词；有回执时优先用回执里存的那份。
        # 同一 thread 分叉成多个 rollout 文件时必须聚合判级（2026-09-23 实测漏判）：
        # 旧实现只看 mtime 最新那个文件，thread 01a0c297 早期峰值 917,686 完全看不见，
        # 于是「到线了却从没触发交接」。
        multi = root / "sessions-multi"
        multi.mkdir()
        write_session(multi / "rollout-old-thread-multi.jsonl", 40_000, 0, 950_000, 30)
        write_session(multi / "rollout-new-thread-multi.jsonl", 40_000, 0, 950_000, 3)
        newest_only = multi / "rollout-new-thread-multi.jsonl"
        assert module.summarize(newest_only)["level"] == "OK", "单个新文件本身确实不该 STOP"
        aggregated = subprocess.run(
            [sys.executable, str(script), "--thread-id", "thread-multi",
             "--sessions-root", str(multi), "--project", str(project), "--read-only"],
            text=True, capture_output=True,
        )
        assert aggregated.returncode == 1, (aggregated.returncode, aggregated.stdout)
        assert "轮次 35 >= 25" in aggregated.stdout, aggregated.stdout
        # 「要在对话框上打印提示词再结束」：STOP 且上轮回复没贴提示词时必须点名。
        assert "上轮回复缺失接力提示词" in aggregated.stdout, aggregated.stdout
        assert "1 个 rollout 文件" not in aggregated.stdout or "2 个 rollout 文件" in aggregated.stdout

        relay = subprocess.run(
            [sys.executable, str(script), "--thread-id", "thread-guard",
             "--print-relay", "--sessions-root", str(sessions), "--project", str(project)],
            text=True, capture_output=True,
        )
        assert relay.returncode == 0, (relay.returncode, relay.stderr)
        assert "project-flow 接力提示词" in relay.stdout, relay.stdout
        assert "--intent" in relay.stdout, relay.stdout
        assert "熔断" in relay.stdout, relay.stdout
        assert "来源：" in relay.stdout and "stop.json" in relay.stdout, relay.stdout

        # --intent 必须能覆盖提示词里那条「触发熔断时的旧意图」：
        # 否则索取提示词时会把旧意图粘给新会话当任务（2026-09-23 实测坑）。
        override = subprocess.run(
            [sys.executable, str(script), "--thread-id", "thread-guard",
             "--print-relay", "--intent", "Wave0：门禁去副作用+菜单恢复",
             "--sessions-root", str(sessions), "--project", str(project)],
            text=True, capture_output=True,
        )
        assert override.returncode == 0, override.stderr
        assert '--intent "Wave0：门禁去副作用+菜单恢复"' in override.stdout, override.stdout
        assert "--intent \"继续当前 project-flow 活跃任务\"" not in override.stdout, override.stdout
    print("PASS: flow-budget classifies OK/WARN/STOP and emits a handoff prompt")


if __name__ == "__main__":
    main()
