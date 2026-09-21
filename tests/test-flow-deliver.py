#!/usr/bin/env python3
"""交付卡最小测试：必须包含改动、验证、证据和 BDD 验收。"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "flow-deliver.py"
spec = importlib.util.spec_from_file_location("flow_deliver", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        card = Path(tmp) / "task.md"
        card.write_text(
            "\n".join(
                [
                    "ticket_id: T-1",
                    "objective: 修正登录失效",
                    "mode: execute",
                    "method: SDD,TDD,ATDD,BDD",
                    "write_whitelist: src/auth.ts,tests/auth.test.ts",
                    "verify_command: npm test -- auth",
                    "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
                    "evidence: tests/auth.test.ts Exit 0",
                ]
            ),
            encoding="utf-8",
        )
        output = module.render(
            module.parse_card(card),
            changed="src/auth.ts,tests/auth.test.ts",
            evidence="npm test -- auth Exit 0",
        )
        assert "实际改动" in output, output
        assert "允许边界" in output, output
        assert "自动验证" in output, output
        assert "验证证据" in output, output
        assert "Given-When-Then" in output, output
        assert "[-] 待人工验收" in output, output
        missing_changed = module.render(module.parse_card(card), changed="", evidence="")
        assert "未提供；不得以 write_whitelist 冒充实际改动" in missing_changed, missing_changed

        plan = Path(tmp) / "plan.md"
        plan.write_text(
            "\n".join(
                [
                    "## 🎯 当前聚焦待办 (P0)",
                    "- [ ] P1-2 后续任务",
                    "## ⏳ 待人工验收",
                    "- [-] T-1 修正登录失效 [🤖 Exit 0][👤 待人工验收]",
                    "## 📦 已完结归档",
                ]
            ),
            encoding="utf-8",
        )
        report = module.render_plan_sections(plan) + "\n" + output
        summary = module.render_work_summary(
            what="修正登录失效",
            why="旧逻辑遗漏续期",
            understanding="仅影响鉴权链路",
            outputs="src/auth.ts,tests/auth.test.ts",
            problem="无",
            next_step="提交人工验收",
        )
        assert "### 📝 本轮工作汇报" in summary, summary
        assert "- 做了什么：修正登录失效" in summary, summary
        assert "- 为什么这么做：旧逻辑遗漏续期" in summary, summary
        assert "- 怎么理解：仅影响鉴权链路" in summary, summary
        assert "- 产出路径：src/auth.ts,tests/auth.test.ts" in summary, summary
        assert "- 下一步：提交人工验收" in summary, summary
        assert "### 📊 任务状态看板" in report, report
        assert "## 🎯 当前聚焦待办 (P0)" in report, report
        assert "## ⏳ 待人工验收" in report, report
        assert "P1-2 后续任务" in report, report
        assert "project-flow 交付验收卡" in report, report

        # 归档卡位于 flow/history/tasks/，必须仍能找到 flow/plan.md。
        flow = Path(tmp) / "flow"
        (flow / "tasks").mkdir(parents=True, exist_ok=True)
        (flow / "history" / "tasks").mkdir(parents=True, exist_ok=True)
        (flow / "plan.md").write_text(
            "\n".join(
                [
                    "## 🎯 当前聚焦待办 (P0)",
                    "- [ ] P1-2 后续任务",
                ]
            ),
            encoding="utf-8",
        )
        archived = flow / "history" / "tasks" / "T-1.md"
        archived.write_text(
            "\n".join(
                [
                    "ticket_id: T-1",
                    "goal: 修正登录失效",
                    "mode: execute",
                    "method: TDD",
                    "write_whitelist: src/auth.ts",
                    "verify_command: npm test -- auth",
                    "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
                    "evidence: tests/auth.test.ts Exit 0",
                ]
            ),
            encoding="utf-8",
        )
        # macOS 的 /var 是 /private/var 软链，比较必须走 resolve()。
        assert module.locate_plan(archived).resolve() == (flow / "plan.md").resolve(), module.locate_plan(archived)
        archived_report = module.render_plan_sections(module.locate_plan(archived))
        assert "plan.md 不存在" not in archived_report, archived_report
        assert "P1-2 后续任务" in archived_report, archived_report

    print("PASS: flow-deliver emits a complete acceptance card")


if __name__ == "__main__":
    main()
