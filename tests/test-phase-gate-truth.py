#!/usr/bin/env python3
"""PFP-PHASE-GATE-TRUTH-20260927：门禁必须读「真实相位」，不得信卡自报的 mode。

缺陷（2026-09-27 真机复现）：
    flow-boot.py:1483   phase = mode if mode in {...} else "plan"
    flow-gate.py:252    if phase == "execute" and mode != "execute": errors.append(...)
两者恒等 → 门禁对任何自报 `mode: execute` 的卡**结构上不可能失败**。
实测后果：6 张卡全部 mode: execute，boot 一律打印「门禁通过 [execute]」，
而它们的 plan 相位（SDD 输入/输出/边界）从未走过。门禁在盖章，不是在守门。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOT = REPO / "scripts" / "flow-boot.py"
GATE = REPO / "scripts" / "flow-gate.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CARD = """ticket_id: {ticket}
schema: v2
objective: 演示用卡
mode: {mode}
method: SDD,TDD,ATDD,BDD
scope: |
  输入：无
  输出：无
  边界：无
write_whitelist: tests/test_dummy.py
verify_command: python3 tests/test_dummy.py
acceptance: Given 无 When 无 Then 无
evidence: tests/test_dummy.py
"""


def make_project(root: Path, plan_body: str, card_body: str, ticket: str) -> Path:
    (root / "flow" / "tasks").mkdir(parents=True)
    (root / "flow" / "history" / "tasks").mkdir(parents=True)
    (root / "flow" / "specs").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "flow" / "plan.md").write_text(plan_body, encoding="utf-8")
    (root / "flow" / "tasks" / f"{ticket}.md").write_text(card_body, encoding="utf-8")
    (root / "tests" / "test_dummy.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return root


def test_phase_from_plan_section_not_card_mode():
    """卡自报 mode: execute，但它在 plan.md 的 `[ ]` 区（=plan 相位）→ 必须判 plan。"""
    boot = load(BOOT, "flow_boot")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ticket = "PFP-DEMO-20260927"
        plan = f"## 🎯 当前聚焦待办 (P0)\n- [ ] {ticket} 演示\n"
        make_project(root, plan, CARD.format(ticket=ticket, mode="execute"), ticket)

        phase = boot.phase_from_plan(root, ticket)
        assert phase == "plan", (
            f"卡在 `[ ]` 区应判 plan 相位，实际 {phase!r}；"
            "说明相位仍取自卡自报的 mode（自证循环未断开）"
        )


def test_gate_blocks_skipping_phases():
    """未交付的卡（`[ ]`）不得自报 review/handoff —— 单向流转不得跳阶段。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ticket = "PFP-DEMO-20260927"
        plan = f"## 🎯 当前聚焦待办 (P0)\n- [ ] {ticket} 演示\n"
        make_project(root, plan, CARD.format(ticket=ticket, mode="review"), ticket)
        card = root / "flow" / "tasks" / f"{ticket}.md"

        result = subprocess.run(
            [sys.executable, str(GATE), str(card), "--phase", "plan"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0, (
            "未交付的卡自报 review 相位，必须被拒（不得跳阶段）；"
            f"实际却通过了：{result.stdout}{result.stderr}"
        )
        assert "单向流转不得跳阶段" in (result.stdout + result.stderr)


def test_execute_card_in_active_area_is_allowed():
    """`[ ]` 区放一张 mode: execute 的卡是合法的（准备实现），门禁不得误杀。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ticket = "PFP-DEMO-20260927"
        plan = f"## 🎯 当前聚焦待办 (P0)\n- [ ] {ticket} 演示\n"
        make_project(root, plan, CARD.format(ticket=ticket, mode="execute"), ticket)
        card = root / "flow" / "tasks" / f"{ticket}.md"

        result = subprocess.run(
            [sys.executable, str(GATE), str(card), "--phase", "plan"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            "`[ ]` 里的实现卡应放行（相位=plan 只表示尚未交付）；"
            f"实际被误杀：{result.stdout}{result.stderr}"
        )


def test_boot_uses_true_phase_not_card_mode():
    """端到端：boot 必须用**真实相位**跑门禁，而不是卡自报的 mode。

    断言方式：放一张自报 mode=review 的卡在 `[ ]` 区。真实相位是 plan，
    因此门禁必须以 [plan] 运行并失败；若 boot 仍拿 mode 当 phase，
    就会以 [review] 运行而放行 —— 这正是自证循环复活的信号。
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ticket = "PFP-DEMO-20260927"
        plan = f"## 🎯 当前聚焦待办 (P0)\n- [ ] {ticket} 演示\n"
        make_project(root, plan, CARD.format(ticket=ticket, mode="review"), ticket)

        result = subprocess.run(
            [sys.executable, str(BOOT), str(root), "--intent", f"{ticket} 演示", "--skip-budget"],
            capture_output=True, text=True,
        )
        combined = result.stdout + result.stderr
        assert "门禁失败 [plan]" in combined, (
            "卡在 `[ ]` 区，门禁必须以真实相位 [plan] 运行并失败；"
            f"实际输出未见「门禁失败 [plan]」——相位很可能仍取自卡自报的 mode。\n{combined}"
        )
        assert "门禁通过 [review]" not in combined, (
            "不得以卡自报的 mode（review）当相位运行门禁——自证循环会复活"
        )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS: {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL: {name}\n      {exc}")
    print("全绿" if not failures else f"{failures} 项失败")
    raise SystemExit(1 if failures else 0)
