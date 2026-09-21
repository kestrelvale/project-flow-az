#!/usr/bin/env python3
"""门禁最小行为测试：占位符不得伪装成有效任务卡，且必须强制四阶段单向门。"""
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
                    "goal: <一句话目标>",
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
        assert any("字段仍为占位符: goal" in error for error in errors), errors
        assert any("字段仍为占位符: scope" in error for error in errors), errors

        card.write_text(
            "\n".join(
                [
                    "ticket_id: T-2",
                    "goal: 实现登录",
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

        # 兼容：旧卡用 objective 代替 goal 仍应放行。
        card.write_text(
            "\n".join(
                [
                    "ticket_id: T-3",
                    "objective: 旧卡目标",
                    "mode: execute",
                    "method: TDD",
                    "write_whitelist: src/auth.ts",
                    "verify_command: python3 tests/auth.py",
                    "acceptance: Given 有效账号，When 登录，Then 成功",
                ]
            ),
            encoding="utf-8",
        )
        assert module.validate(card, "execute") == [], module.validate(card, "execute")

        # 两别名都缺失时必须失败。
        card.write_text(
            "\n".join(
                [
                    "ticket_id: T-4",
                    "mode: execute",
                    "method: TDD",
                    "write_whitelist: src/auth.ts",
                    "verify_command: python3 tests/auth.py",
                    "acceptance: Given 有效账号，When 登录，Then 成功",
                ]
            ),
            encoding="utf-8",
        )
        assert any("缺少字段: goal" in error for error in module.validate(card, "execute"))

        # 四阶段各自的关键必填字段与驱动模式必须对齐。
        cases = [
            ("plan", "SDD", ("scope", "write_whitelist"), "scope"),
            ("execute", "TDD", ("verify_command",), "verify_command"),
            ("review", "ATDD", ("evidence",), "evidence"),
            ("handoff", "BDD", ("next_agent", "next_action"), "next_agent"),
        ]
        for phase, method, required_keys, absent_key in cases:
            values = {
                "ticket_id": f"T-{phase}",
                "goal": f"{phase} 目标",
                "mode": phase,
                "method": method,
                "scope": "输入输出边界",
                "write_whitelist": "flow/tasks",
                "verify_command": "python3 check.py",
                "acceptance": "Given 前提，When 操作，Then 结果",
                "evidence": "check.py Exit 0",
                "next_agent": "Codex Execute Mode",
                "next_action": "执行下一步",
            }
            for key in required_keys:
                assert key in values
            complete = "\n".join(f"{key}: {value}" for key, value in values.items())
            card.write_text(complete, encoding="utf-8")
            assert module.validate(card, phase) == [], (phase, module.validate(card, phase))
            missing = "\n".join(
                line for line in complete.splitlines() if not line.startswith(f"{absent_key}:")
            )
            card.write_text(missing, encoding="utf-8")
            errors = module.validate(card, phase)
            assert any(absent_key in error for error in errors), (phase, errors)

    print("PASS: flow-gate enforces four-phase modes and goal alias")


if __name__ == "__main__":
    main()
