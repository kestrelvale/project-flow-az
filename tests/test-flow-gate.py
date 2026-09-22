#!/usr/bin/env python3
"""门禁最小行为测试：占位符不得伪装成有效任务卡，且必须强制四阶段单向门。"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_fixtures import write_block_scalar_card

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

        # 块标量字段必须拼回正文，不能把 `>` 当成字段值。
        write_block_scalar_card(card)
        parsed = module.parse_card(card)
        # 块标量按行保留，便于多行路径清单后续按行拆分。
        assert parsed["verify_command"] == "python3 tests/a.py\n&& echo done", parsed
        assert parsed["acceptance"] == "Given A\nWhen B\nThen C", parsed
        assert module.validate(card, "execute") == [], module.validate(card, "execute")

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

        # v2 严格模式：Plan/SDD/TDD/ATDD/BDD 必须留下真实产物。
        root = Path(tmp)
        (root / "flow" / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests" / "test_x.py").write_text("assert True\n", encoding="utf-8")
        (root / "evidence.txt").write_text("Exit 0\n", encoding="utf-8")
        v2 = root / "flow" / "tasks" / "V2.md"

        def write_v2(**over: str) -> None:
            base = {
                "ticket_id": "V2-1",
                "schema": "v2",
                "goal": "严格门禁演示",
                "mode": "plan",
                "method": "SDD,TDD,ATDD,BDD",
                "scope": "输入：x\n输出：y\n边界：z",
                "write_whitelist": "tests/test_x.py",
                "red_test": "tests/test_x.py",
                "verify_command": "python3 tests/test_x.py",
                "acceptance": "Given A，When B，Then C",
                "evidence": "evidence.txt",
                "next_agent": "Codex Execute Mode",
                "next_action": "执行下一步",
            }
            base.update(over)
            v2.write_text("\n".join(f"{k}: {v}" for k, v in base.items()), encoding="utf-8")

        # SDD：scope 缺“边界”必须 FAIL。
        write_v2(scope="输入：x\n输出：y")
        assert any("SDD 规格不完整" in e for e in module.validate(v2, "plan")), module.validate(v2, "plan")

        # TDD：red_test 指向不存在的文件必须 FAIL。
        write_v2(mode="execute", method="TDD", red_test="tests/nope.py")
        assert any("red_test 指向的文件不存在" in e for e in module.validate(v2, "execute"))

        # TDD：red_test 真实存在则通过。
        write_v2(mode="execute", method="TDD")
        assert module.validate(v2, "execute") == [], module.validate(v2, "execute")

        # TDD：存在但不是测试文件（如 README）必须 FAIL——防“随便指一个文件”绕过。
        (root / "README.md").write_text("说明文档\n", encoding="utf-8")
        write_v2(mode="execute", method="TDD", red_test="README.md")
        assert any("不是测试文件或不含断言" in e for e in module.validate(v2, "execute")), module.validate(v2, "execute")

        # TDD：路径像测试但正文没有断言，同样必须 FAIL。
        (root / "tests" / "empty_test.py").write_text("x = 1\n", encoding="utf-8")
        write_v2(mode="execute", method="TDD", red_test="tests/empty_test.py")
        assert any("不是测试文件或不含断言" in e for e in module.validate(v2, "execute")), module.validate(v2, "execute")

        # ATDD：证据文件不存在必须 FAIL。
        write_v2(mode="review", method="ATDD", evidence="missing.txt")
        assert any("ATDD 证据文件不存在" in e for e in module.validate(v2, "review"))

        # BDD：验收必须写成 Given-When-Then。
        write_v2(mode="review", method="ATDD", acceptance="已经验证过了")
        assert any("Given-When-Then" in e for e in module.validate(v2, "review"))

        # 老卡无 schema：同样内容不应被严格规则拦下。
        v2.write_text(
            "\n".join(
                [
                    "ticket_id: OLD-1",
                    "goal: 老卡",
                    "mode: plan",
                    "method: SDD",
                    "scope: 输入输出边界",
                    "write_whitelist: tests/test_x.py",
                    "acceptance: Given A，When B，Then C",
                ]
            ),
            encoding="utf-8",
        )
        assert module.validate(v2, "plan") == [], module.validate(v2, "plan")

    print("PASS: flow-gate enforces four-phase modes, goal alias and v2 artifacts")


if __name__ == "__main__":
    main()
