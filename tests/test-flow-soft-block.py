#!/usr/bin/env python3
"""预算 STOP 未交接时必须柔性阻塞：路由降级为 handoff-only，补交接后自动解除。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "flow-boot.py"


def boot(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BOOT),
            str(root),
            "--intent",
            "登录状态修复",
            "--skip-budget",
            "--thread-id",
            "01a0c6f8-324a-7112-82de-d0f97e2f21d4",
        ],
        text=True,
        capture_output=True,
    )


def main() -> None:
    uid = "01a0c6f8-324a-7112-82de-d0f97e2f21d4"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow = root / "flow"
        (flow / "tasks").mkdir(parents=True)
        (flow / "history").mkdir()
        (flow / "trash").mkdir()
        (flow / "规范").mkdir()
        (flow / "规范" / "VERSION").write_text(
            (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (flow / "plan.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "## 当前聚焦待办 (P0)",
                    "- [ ] T1 [登录状态修复] 修正登录失效",
                ]
            ),
            encoding="utf-8",
        )
        for name in ("charter.md", "decisions.md", "踩坑记录.md"):
            (flow / name).write_text("", encoding="utf-8")
        (flow / "进展.md").write_text(
            "## 2026-09-22 · 旧交接棒 · T1\n- 现状: 旧\n", encoding="utf-8"
        )
        (flow / "tasks" / "T1-login.md").write_text(
            "\n".join(
                [
                    "ticket_id: T1",
                    "objective: 修正登录失效",
                    "mode: execute",
                    "method: SDD,TDD,ATDD,BDD",
                    "scope: 输入=登录请求；输出=有效令牌",
                    "write_whitelist: src/auth.ts,tests/auth.test.ts",
                    "verify_command: npm test -- auth",
                    "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
                ]
            ),
            encoding="utf-8",
        )
        # 上一轮熔断回执：交接棒标题未变 = 尚未交接。
        receipts = flow / "budget"
        receipts.mkdir()
        (receipts / "20260923-120000-stop.json").write_text(
            json.dumps(
                {
                    "operation": "budget_stop",
                    "input_tokens": 300_000,
                    "rounds": 23,
                    "tool_calls": 160,
                    "reasons": ["上下文占用 31.6%"],
                    "handoff_head": "## 2026-09-22 · 旧交接棒 · T1",
                    "thread_id": "01a0c6f8-324a-7112-82de-d0f97e2f21d4",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        blocked = boot(root)
        assert "【柔性阻塞】" in blocked.stdout, blocked.stdout
        assert "Handoff 路由（柔性阻塞）" in blocked.stdout, blocked.stdout
        assert "拒绝登记新意图" in blocked.stdout, blocked.stdout
        assert "Execute 路由" not in blocked.stdout, blocked.stdout
        assert blocked.returncode == 0, blocked.returncode  # 柔性：进程不失败

        # 绕过回归：只改标题、正文空洞的交接棒**不得**核销熔断。
        # 实测过：写一句 `## 2026-09-23 · T1 · 交了` + `- 干了点活` 就能解锁继续施工，
        # 那样整个柔性阻塞形同虚设。核销必须走蒸馏/字段校验。
        (flow / "进展.md").write_text(
            "## 2026-09-23 · T1 · 交了\n- 干了点活\n", encoding="utf-8"
        )
        bypass = boot(root)
        assert "【柔性阻塞】" in bypass.stdout, bypass.stdout
        assert "Handoff 路由（柔性阻塞）" in bypass.stdout, bypass.stdout

        # 补上 SDD 蒸馏交接棒 → 熔断回执被核销，阻塞自动解除。
        (flow / "进展.md").write_text(
            "\n".join(
                [
                    "## 2026-09-23 · T1 · 交接棒（SDD 蒸馏） · thread=01a0c6f8-324a-7112-82de-d0f97e2f21d4",
                    "- 规格点 SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
                    "- 还剩：SPE-2",
                    "- 卡在哪：无",
                    "- 下一步：开新会话按未回收规格点继续",
                    "",
                    "## 2026-09-22 · 旧交接棒 · T1",
                    "- 现状: 旧",
                ]
            ),
            encoding="utf-8",
        )


        # 反向：来源会话对不上的交接棒**不得**核销（实测踩过：并发会话顶掉别人的交接棒）
        (flow / "进展.md").write_text(
            "\n".join(
                [
                    "## 2026-09-23 · T1 · 别人的交接棒 · thread=deadbeef-0000-4000-8000-000000000000",
                    "- 规格点 SPE-1 | x | 证据：y",
                    "- 现状：别人写的",
                    "- 还剩：无",
                    "- 卡在哪：无",
                    "- 下一步：无",
                    "",
                    '## 2026-09-22 · 旧交接棒 · T1',
                    "- 现状: 旧",
                ]
            ),
            encoding="utf-8",
        )
        # 先把回执恢复成未核销状态
        import json as _json
        (receipts / "20260923-130000-stop.json").write_text(
            _json.dumps(
                {
                    "operation": "budget_stop",
                    "input_tokens": 300_000,
                    "rounds": 23,
                    "tool_calls": 160,
                    "reasons": ["上下文占用 31.6%"],
                    "handoff_head": "## 2026-09-22 · 旧交接棒 · T1",
                    "thread_id": "01a0c6f8-324a-7112-82de-d0f97e2f21d4",
                    "thread_id": "01a0c6f8-324a-7112-82de-d0f97e2f21d4",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        foreign = boot(root)
        assert "【柔性阻塞】" in foreign.stdout, foreign.stdout
        assert "未核销原因" in foreign.stdout, foreign.stdout
        assert "只有当事会话写的交接棒" in foreign.stdout, foreign.stdout
        # 第5点：交接棒被并发会话顶到下面时，仍必须核销（否则那两个会话永远卡死）。
        # 实测 2026-09-23：顶部是别的会话的交接棒，本会话自己的那条被挤到第 2 条。
        (flow / "进展.md").write_text(
            "\n".join([
                "## 2026-09-23 · 别人的交接棒 · thread=deadbeef-0000-4000-8000-000000000000",
                "- 规格点 SPE-9 | 别人的活 | 证据：x",
                "- 现状：别人写的", "- 还剩：无", "- 卡在哪：无", "- 下一步：无",
                "",
                f"## 2026-09-23 · T1 · 我的交接棒（SDD 蒸馏） · thread={uid}",
                "- 规格点 SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
                "- 现状：已交接", "- 还剩：无", "- 卡在哪：无", "- 下一步：开新会话",
                "",
                "## 2026-09-22 · 旧交接棒 · T1", "- 现状: 旧",
            ]) + "\n",
            encoding="utf-8",
        )
        # 先把回执恢复成未核销
        (receipts / "20260923-140000-stop.json").write_text(
            json.dumps({"operation": "budget_stop", "input_tokens": 300_000, "rounds": 23,
                        "tool_calls": 160, "reasons": ["工具调用 160 >= 160"],
                        "handoff_head": "## 2026-09-22 · 旧交接棒 · T1",
                        "thread_id": uid}, ensure_ascii=False), encoding="utf-8")
        displaced = boot(root)
        assert "【柔性阻塞】" not in displaced.stdout, displaced.stdout
        assert "已被并发会话顶掉" in displaced.stdout, displaced.stdout

        # 补上「当事会话」写的交接棒（带 thread=<uid>）→ 熔断回执被核销，阻塞自动解除。
        (flow / "进展.md").write_text(
            "\n".join(
                [
                    "## 2026-09-23 · T1 · 交接棒（SDD 蒸馏） · thread=01a0c6f8-324a-7112-82de-d0f97e2f21d4",
                    "- 规格点 SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
                    "- 现状：已交接",
                    "- 还剩：SPE-2",
                    "- 卡在哪：无",
                    "- 下一步：开新会话按未回收规格点继续",
                    "",
                    "## 2026-09-22 · 旧交接棒 · T1",
                    "- 现状: 旧",
                ]
            ),
            encoding="utf-8",
        )
        released = boot(root)
        assert "【柔性阻塞】" not in released.stdout, released.stdout
        assert "Execute 路由" in released.stdout, released.stdout
    print("PASS: soft block routes handoff-only and clears after the handoff lands")


if __name__ == "__main__":
    main()
