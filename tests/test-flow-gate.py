#!/usr/bin/env python3
"""门禁最小行为测试：模板占位符不得伪装成有效任务卡。"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "flow-gate.py"
spec = importlib.util.spec_from_file_location("flow_gate", SCRIPT)
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
                    "objective: <一句话目标>",
                    "mode: plan",
                    "method: SDD",
                    "scope: <边界>",
                    "write_whitelist: flow/tasks",
                    "acceptance: <验收>",
                ]
            ),
            encoding="utf-8",
        )
        errors = module.validate(card, "plan")
        assert any("字段仍为占位符: objective" in error for error in errors), errors
        assert any("字段仍为占位符: scope" in error for error in errors), errors

        card.write_text(
            "\n".join(
                [
                    "ticket_id: T-2",
                    "objective: 实现登录",
                    "mode: execute",
                    "method: SDD",
                    "scope: 登录输入输出边界",
                    "write_whitelist: src/auth.ts",
                    "acceptance: Given 有效账号，When 登录，Then 成功",
                ]
            ),
            encoding="utf-8",
        )
        errors = module.validate(card, "plan")
        assert "plan 阶段 mode 必须为 plan" in errors, errors
    print("PASS: flow-gate rejects placeholder task cards")


if __name__ == "__main__":
    main()
