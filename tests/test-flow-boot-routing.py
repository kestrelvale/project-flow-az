#!/usr/bin/env python3
"""开工入口必须路由活跃任务、任务卡和本轮意图。"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "flow-boot.py"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow = root / "flow"
        tasks = flow / "tasks"
        tasks.mkdir(parents=True)
        (flow / "history").mkdir()
        (flow / "trash").mkdir()
        (flow / "规范").mkdir()
        (flow / "规范" / "VERSION").write_text(
            (ROOT / "VERSION").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (flow / "plan.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "## 当前聚焦待办 (P0)",
                    "- [ ] P0-1 [登录状态修复] 修正登录失效",
                    "- [ ] P0-2 [支付计划] 只做支付方案规划",
                    "- [-] P0-3 [登录交付] 已自动验证，待人工验收",
                    "## 后续排队待办 (Backlog)",
                    "- [ ] P9-9 [不应路由] 旧 backlog",
                ]
            ),
            encoding="utf-8",
        )
        for name in ("进展.md", "charter.md", "decisions.md", "踩坑记录.md"):
            (flow / name).write_text("", encoding="utf-8")
        (tasks / "P0-1-login.md").write_text(
            "\n".join(
                [
                    "ticket_id: P0-1",
                    "objective: 修正登录失效",
                    "mode: execute",
                    "method: SDD,TDD,ATDD,BDD",
                    "scope: 输入=登录请求；输出=有效令牌；失败态=拒绝无效请求",
                    "write_whitelist: src/auth.ts,tests/auth.test.ts",
                    "verify_command: npm test -- auth",
                    "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
                    "evidence: tests/auth.test.ts Exit 0",
                    "next_agent: Codex Execute Mode",
                    "next_action: 先写回归测试再修复",
                ]
            ),
            encoding="utf-8",
        )
        (tasks / "P0-2-payment-plan.md").write_text(
            "\n".join(
                [
                    "ticket_id: P0-2",
                    "objective: 只做支付方案规划",
                    "mode: plan",
                    "method: SDD",
                    "scope: 输入=支付需求；输出=规划；边界=只读",
                    "write_whitelist: flow/tasks",
                    "acceptance: Given 支付需求，When 规划，Then 给出方案",
                ]
            ),
            encoding="utf-8",
        )
        nested = tasks / "mobile"
        nested.mkdir()
        (nested / "P1-1-mobile.md").write_text(
            "\n".join(
                [
                    "ticket_id: P1-1",
                    "objective: 移动端子任务",
                    "mode: plan",
                    "method: SDD",
                    "scope: 输入=需求；输出=计划；边界=只读",
                    "write_whitelist: flow/tasks/mobile",
                    "verify_command: python3 -m py_compile plan.py",
                    "acceptance: Given 需求，When 规划，Then 给出原子任务",
                ]
            ),
            encoding="utf-8",
        )
        boot = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                "登录状态修复",
                "--thread-id",
                "test-thread-project-flow-routing",
            ],
            text=True,
            capture_output=True,
        )
        assert boot.returncode == 0, boot
        assert "P0-1" in boot.stdout, boot.stdout
        assert "P1-1" in boot.stdout, boot.stdout
        routing_lines = [
            line
            for line in boot.stdout.splitlines()
            if line.startswith(
                ("- 路由: Plan 路由：", "- 路由: Execute 路由：", "- 路由: Handoff 路由：")
            )
        ]
        assert not any("P9-9" in line for line in routing_lines), boot.stdout
        assert "未纳管遗留" in boot.stdout and "P9-9" in boot.stdout, boot.stdout
        assert "Execute 路由" in boot.stdout, boot.stdout
        assert "Plan 路由" in boot.stdout and "P0-2" in boot.stdout, boot.stdout
        assert "项目初期阶段：只读执行 Plan / Goal / SDD 规划门" in boot.stdout, boot.stdout
        assert "实现阶段：先写失败测试再最小实现 (TDD)" in boot.stdout, boot.stdout
        assert "静默任务卡" in boot.stdout and "P1-1" in boot.stdout, boot.stdout
        assert "本轮意图已绑定任务卡" in boot.stdout, boot.stdout
        assert "P1-1 | 未绑定活跃区" in boot.stdout, boot.stdout
        assert "### project-flow 开工状态" in boot.stdout, boot.stdout
        assert "## 🎯 当前聚焦待办 (P0)" in boot.stdout, boot.stdout
        assert "## 🚧 路由阻塞" in boot.stdout, boot.stdout
        assert "## 🧹 未纳管遗留" in boot.stdout, boot.stdout
        assert "## 🧾 只读状态计数" in boot.stdout, boot.stdout
        assert "- 待验收：1" in boot.stdout, boot.stdout
        assert "## ⚠️ 待人工决策" in boot.stdout, boot.stdout
        assert "## ♻️ 回收建议" in boot.stdout, boot.stdout
        assert "待验收积压 1 项" in boot.stdout, boot.stdout
        assert "不得自动标记通过" in boot.stdout, boot.stdout
        assert "孤儿任务卡 1 张" in boot.stdout, boot.stdout
        assert "P1-1" in boot.stdout.split("## ♻️ 回收建议")[1], boot.stdout
        assert "## ⏳ 待人工验收" not in boot.stdout, boot.stdout
        assert "## 📦 已完结归档" not in boot.stdout, boot.stdout
        assert "## 💡 本轮决策" not in boot.stdout, boot.stdout

        # plan.md 归档区堆积超过阈值时，必须在回收建议里暴露，避免静默膨胀。
        (flow / "plan.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "## 当前聚焦待办 (P0)",
                    "- [ ] P0-1 [登录状态修复] 修正登录失效",
                    "## 📦 本阶段已完成归档 (Archived)",
                    *[f"- 已归档历史条目 {i} " + "补" * 60 for i in range(20)],
                ]
            ),
            encoding="utf-8",
        )
        bloated = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                "登录状态修复",
                "--skip-budget",
            ],
            text=True,
            capture_output=True,
        )
        assert "已终结内容应物理剪切到 flow/history/" in bloated.stdout, bloated.stdout

        unregistered = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                "新增完全未登记的功能",
                "--thread-id",
                "test-thread-project-flow-routing",
            ],
            text=True,
            capture_output=True,
        )
        assert "project-flow SDD 登记门" in unregistered.stdout, unregistered.stdout
        assert "先留下一个能因缺陷而失败的检查" in unregistered.stdout, unregistered.stdout
        assert "--phase plan" in unregistered.stdout, unregistered.stdout

        skipped = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                "登录状态修复",
                "--skip-budget",
            ],
            text=True,
            capture_output=True,
        )
        assert skipped.returncode == 0, skipped
        assert "project-flow 预算" not in skipped.stdout, skipped.stdout
        assert "project-flow 接管路由" in skipped.stdout, skipped.stdout
        assert "### project-flow 开工状态" in skipped.stdout, skipped.stdout

        outside = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                "/tmp",
                "--intent",
                "不在项目目录",
            ],
            text=True,
            capture_output=True,
        )
        assert outside.returncode == 1, outside
        assert "未接管" in outside.stdout, outside.stdout
        assert "不属于任何已接入项目" in outside.stdout, outside.stdout
    print("PASS: flow-boot routes active focus, task cards, nested cards and intent")


if __name__ == "__main__":
    main()
