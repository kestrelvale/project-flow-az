#!/usr/bin/env python3
"""任务卡模板回归：模板必须自带 v2 门禁所需字段，且填充后四阶段全部放行。

同时校验方法论已吸收进模板：SDD 六段、TDD 五拍、ATDD 可执行断言、BDD Given-When-Then。
"""
from __future__ import annotations

import importlib.util
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "assets" / "templates" / "flow" / "tasks" / "TEMPLATE.md"
GATE = ROOT / "scripts" / "flow-gate.py"

spec = importlib.util.spec_from_file_location("flow_gate", GATE)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

PLACEHOLDERS = {
    "<一句话目标：可观察的结果，不是做法>": "演示目标",
    "<触发方式、字段、有效与无效边界>": "输入 x",
    "<返回值、界面状态、文件或日志变化>": "输出 y",
    "<不做的事与失败状态>": "边界 z",
    "<允许修改的文件或目录>": "tests/test_x.py",
    "<前置任务 ticket_id；多个用逗号分隔，无则留空或写 无>": "无",
    "<execute 阶段先失败的测试文件路径，先红后绿>": "tests/test_x.py",
    "<可复现的 Exit 0 验证命令>": "python3 tests/test_x.py",
    "<Given-When-Then 或可执行验收断言>": "Given A，When B，Then C",
    "<验证凭证路径，交付前填写>": "ev.txt",
    "<交接给下一模式的第一个动作>": "执行",
}


def main() -> None:
    text = TPL.read_text(encoding="utf-8")

    # 模板必须自带严格模式标记与各阶段字段名。
    assert "schema: v2" in text, "模板缺 schema: v2"
    for field in (
        "red_test:",
        "verify_command:",
        "evidence:",
        "write_whitelist:",
        "depends_on:",
        "spec_ledger:",
    ):
        assert field in text, f"模板缺字段 {field}"
    assert "规格点" in text, "模板未吸收规格点回收要求"

    # 出厂台账模板必须存在，且行格式与 flow-gate / flow-distill 的正则一致。
    ledger_tpl = ROOT / "assets" / "templates" / "flow" / "specs" / "TEMPLATE.md"
    assert ledger_tpl.is_file(), "缺出厂规格点台账模板 flow/specs/TEMPLATE.md"
    ledger_text = ledger_tpl.read_text(encoding="utf-8")
    assert re.search(r"^-\s*\[[ x\-!]\]\s*SPE-\d+\s*\|.*\|\s*证据：", ledger_text, re.M), (
        "台账模板的示例行不符合门禁正则"
    )

    # 方法论必须被吸收进模板本体，而不是只写在别处。
    for marker in ("用户故事", "测试决策", "五拍循环", "Given-When-Then", "按需深挖"):
        assert marker in text, f"模板未吸收方法论：{marker}"

    # 填充全部占位符后，四阶段门禁都必须放行。
    filled = text
    for key, value in PLACEHOLDERS.items():
        filled = filled.replace(key, value)
    assert "<" not in filled.split("## Plan")[0].replace("<br>", ""), "仍有未替换的占位符"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "flow" / "tasks").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "tests" / "test_x.py").write_text("assert True\n", encoding="utf-8")
        (root / "ev.txt").write_text("Exit 0\n", encoding="utf-8")
        # 模板声明了 spec_ledger: flow/specs/P0-1.md，进 review 前台账必须存在且已回收。
        (root / "flow" / "specs").mkdir(parents=True)
        (root / "flow" / "specs" / "P0-1.md").write_text(
            "- [x] SPE-1 | 演示目标达成 | 证据：tests/test_x.py Exit 0\n", encoding="utf-8"
        )
        card = root / "flow" / "tasks" / "T.md"
        for phase in ("plan", "execute", "review", "handoff"):
            # 模板默认 mode: plan，逐阶段切换 mode 后再验门禁。
            card.write_text(
                filled.replace("mode: plan", f"mode: {phase}", 1), encoding="utf-8"
            )
            errors = gate.validate(card, phase)
            assert errors == [], (phase, errors)

    print("PASS: task template carries v2 fields and absorbed methodologies")


if __name__ == "__main__":
    main()
