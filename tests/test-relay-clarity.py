#!/usr/bin/env python3
"""交接要「说清楚」：接力提示词必须自包含工作根与具体 ticket，交接棒不再被体积拦。

事故（2026-09-24 实测 thread 01a0d08b）：
用户把 wt-p4 的接力提示词贴进**主仓**新会话，提示词里只写 `flow/plan.md` /
`flow/tasks/<ticket>.md`（相对路径 + 占位符，且没写工作根是 wt-p4），
于是新会话先读主仓的 plan/进展（那是别的任务的 DAILY-OPTIONS 交接棒），
再自己去 `git worktree list` / claims / 源码里找 P4 到底在哪 → 75 次工具调用遍读历史。
同时「单条交接棒 ≤1200/4000 字节」的旧判据仍在文档与代码里，逼着把交接写成压缩包。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "flow-boot.py"
BUDGET = ROOT / "scripts" / "flow-budget.py"
TICKET = "W2-P4-CANDIDATE-H5-20260922"
UID = "01a0c1cd-a264-7321-8779-8440e6de59ac"


def build(root: Path) -> Path:
    flow = root / "flow"
    for name in ("tasks", "history", "trash", "budget", "specs", "gc/receipts"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范").mkdir()
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "\n".join(
            [
                "# Plan",
                "## 当前聚焦待办 (P0)",
                f"- [ ] {TICKET} [P4] 求职者 H5 收口",
            ]
        ),
        encoding="utf-8",
    )
    for name in ("charter.md", "decisions.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    # 交接棒：结构化合规 + 引用具体 ticket；尾巴足够长（>4000 字节）以覆盖体积判据。
    handoff = "\n".join(
        [
            f"## 2026-09-24 · {TICKET} · 交接棒（SDD 蒸馏） · thread={UID}",
            "- 来源会话：thread=" + UID,
            "- 规格点(SPE)：SPE-1 基线｜SPE-2 走查",
            "- 待办(TODO)：- [x] SPE-1｜- [ ] SPE-2",
            "- 现状：脚本级全链路 Exit 0；本轮预算熔断，仅落盘交接。",
            "- 还剩：SPE-2 浏览器走查与截图。",
            "- 卡在哪：无。",
            "- 下一步：按台账 SPE-2 施工。",
            f"- 台账：flow/specs/{TICKET}.md",
            "",
            "- 逐页明细（必要时写全，不为了省字节而丢信息）：",
            *[f"  - 页面 {index:03d}：四态/接口/证据逐条列明。" for index in range(1, 200)],
        ]
    )
    (flow / "进展.md").write_text(handoff + "\n", encoding="utf-8")
    (flow / "tasks" / f"{TICKET}.md").write_text(
        "\n".join(
            [
                f"ticket_id: {TICKET}",
                "objective: 求职者 H5 收口",
                "mode: execute",
                "method: SDD,TDD,ATDD,BDD",
                "scope: 输入=矩阵；输出=页面；边界=不改共享文件",
                "write_whitelist: src/zhengjie-mobile/src/subpackages/candidate/**",
                "verify_command: python3 scripts/verify_zhengjie_candidate_h5.py",
                "acceptance: Given 矩阵 25 行，When 收口，Then 逐行有四态",
            ]
        ),
        encoding="utf-8",
    )
    (flow / "specs" / f"{TICKET}.md").write_text(
        f"- [ ] SPE-2 | 浏览器走查 | 证据：\n", encoding="utf-8"
    )
    return flow


def write_session(path: Path, input_tokens: int, window: int, turns: int) -> None:
    """最小 rollout：让 --print-relay 的降级路径能解析到会话（复用 test-flow-budget 的写法）。"""
    stem = path.stem
    with path.open("w", encoding="utf-8") as handle:
        for index in range(turns):
            handle.write(
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "task_started",
                            "turn_id": f"{stem}-turn-{index}",
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
                            "cached_input_tokens": 0,
                            "output_tokens": 100,
                            "total_tokens": input_tokens + 100,
                        },
                        "thread_token_usage": {
                            "input_tokens": input_tokens * turns,
                            "cached_input_tokens": 0,
                        },
                    },
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def relay(root: Path, sessions: Path, intent: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BUDGET),
            "--print-relay",
            "--project",
            str(root),
            "--thread-id",
            UID,
            "--intent",
            intent,
            "--sessions-root",
            str(sessions),
        ],
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow = build(root)
        handoff_bytes = len((flow / "进展.md").read_bytes())
        assert handoff_bytes > 4000, handoff_bytes
        sessions = root / "sessions" / "2026" / "09" / "24"
        sessions.mkdir(parents=True)
        write_session(sessions / f"rollout-2026-09-24T07-13-00-{UID}.jsonl", 120_000, 950_000, 3)
        # 回执是 v4.15.4 之前那种「没带 handoff_prompt」的老回执 → 走实时生成降级路径，
        # 这正是「换会话后想拿回提示词/生成新提示词」的真实入口。
        (flow / "budget" / "20260923-120000-stop.json").write_text(
            json.dumps(
                {
                    "operation": "budget_stop",
                    "thread_id": UID,
                    "input_tokens": 300_000,
                    "rounds": 22,
                    "tool_calls": 200,
                    "reasons": ["工具调用 200 >= 160"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # SPE-1：交接棒再长也不得被体积判据拦下（防复述由照抄检测承担）。
        # 夹具交接棒带「熔断」字样 → check_handoff_schema 真正生效（否则本条断言会假绿）。
        assert "熔断" in (flow / "进展.md").read_text(encoding="utf-8")
        boot = subprocess.run(
            [sys.executable, str(BOOT), str(root), "--intent", f"{TICKET} 收口", "--skip-budget"],
            text=True,
            capture_output=True,
        )
        assert "字节（上限" not in boot.stdout, boot.stdout[-800:]

        # SPE-3 负向：撤掉体积判据不等于把结构校验一起删掉 —— 漏字段仍必须报。
        body = (flow / "进展.md").read_text(encoding="utf-8").replace("- 下一步：", "- 后续：")
        (flow / "进展.md").write_text(body, encoding="utf-8")
        broken = subprocess.run(
            [sys.executable, str(BOOT), str(root), "--intent", f"{TICKET} 收口", "--skip-budget"],
            text=True,
            capture_output=True,
        )
        assert "交接棒缺少字段" in broken.stdout, broken.stdout[-800:]

        # SPE-2：接力提示词必须自包含 —— 工作根绝对路径 + 具体 ticket 的 tasks/specs 路径。
        prompt = relay(root, root / "sessions", f"{TICKET} 收口")
        assert prompt.returncode == 0, (prompt.returncode, prompt.stderr)
        text = prompt.stdout
        resolved = str(root.resolve())
        assert resolved in text, text[-1200:]
        assert f"{resolved}/flow/tasks/{TICKET}.md" in text, text[-1200:]
        assert f"{resolved}/flow/specs/{TICKET}.md" in text, text[-1200:]
        # 只读取清单里不得再出现占位符（模板段落里的 <ticket> 是给新交接棒用的，允许保留）
        assert "flow/tasks/<ticket>.md" not in text, text[-1200:]
        assert "flow/specs/<ticket>.md 里状态" not in text, text[-1200:]
        assert "工作根" in text, text[-1200:]

        # SPE-3 负向：识别不出 ticket 时保留占位符、提示词仍可用（不崩、不阻塞）。
        (flow / "进展.md").write_text(
            "## 2026-09-24 · 交接棒（SDD 蒸馏） · thread=" + UID + "\n- 现状：x\n",
            encoding="utf-8",
        )
        fallback = relay(root, root / "sessions", "无 ticket 场景")
        assert fallback.returncode == 0, (fallback.returncode, fallback.stderr)
        assert "flow/tasks/<ticket>.md" in fallback.stdout, fallback.stdout[-800:]
        assert str(root.resolve()) in fallback.stdout, fallback.stdout[-800:]
    print("PASS: relay prompt is self-contained; handoff size no longer blocks")


if __name__ == "__main__":
    main()
