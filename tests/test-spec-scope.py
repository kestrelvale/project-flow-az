#!/usr/bin/env python3
"""PFP-SPEC-ACCUMULATION-20260928：规格点不得跨任务累积加载。

缺陷（2026-09-28 真机复现）：
    flow-boot.py 调 `flow-distill spec --project <root>` **不传 --ticket** →
    flow-distill 走 `specs_dir.glob("*.md")` 扫**全部**台账 →
    把前 25 行塞进**每个会话的首屏**。

实测：12 张台账共 49 条规格点，全新会话开工首屏出现 25 行 `SPE-`，
其中 9 张台账的主卡**早已归档**（且 0 条未回收）——纯粹是历史垃圾。
用户看到「挂了很多规格点，但我一次任务没这么多」正是此故。

设计意图（用户 2026-09-28 明确）：
    规格点是 plan 的子任务。做完 → 下轮不加载；没做完 → 下轮继续加载。
    即：加载范围必须是**本次要接的那张卡**。
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOT = REPO / "scripts" / "flow-boot.py"
DISTILL = REPO / "scripts" / "flow-distill.py"


def make_project(root: Path) -> Path:
    (root / "flow" / "specs").mkdir(parents=True)
    (root / "flow" / "tasks").mkdir(parents=True)
    (root / "flow" / "history" / "tasks").mkdir(parents=True)
    (root / "flow" / "plan.md").write_text(
        "## 🎯 当前聚焦待办 (P0)\n- [ ] T-CUR 当前卡\n", encoding="utf-8"
    )
    (root / "flow" / "tasks" / "T-CUR.md").write_text(
        "ticket_id: T-CUR\nobjective: 当前卡\nmode: execute\n"
        "method: SDD,TDD,ATDD,BDD\nscope: 输入=无；输出=无；边界=无\n"
        "write_whitelist: tests/x.py\nverify_command: python3 tests/x.py\n"
        "acceptance: Given 无 When 无 Then 无\nred_test: tests/x.py\n",
        encoding="utf-8",
    )
    # 本卡：1 条未回收
    (root / "flow" / "specs" / "T-CUR.md").write_text(
        "# 台账 · T-CUR\n"
        "- [ ] SPE-1 | 本卡未回收项 | 证据：\n",
        encoding="utf-8",
    )
    # 历史垃圾：3 张已归档卡的台账（全部已回收，却仍留在 flow/specs/）
    for i in range(1, 4):
        tk = f"T-OLD{i}"
        (root / "flow" / "history" / "tasks" / f"{tk}.md").write_text(
            f"ticket_id: {tk}\n", encoding="utf-8"
        )
        (root / "flow" / "specs" / f"{tk}.md").write_text(
            f"# 台账 · {tk}\n"
            f"- [x] SPE-1 | 历史卡旧项{i} | 已完成 | 证据：x\n"
            f"- [x] SPE-2 | 历史卡旧项{i}b | 已完成 | 证据：x\n",
            encoding="utf-8",
        )
    return root


def _load_boot():
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader("flow_boot", str(BOOT))
    mod = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("flow_boot", loader)
    )
    loader.exec_module(mod)
    return mod


def test_no_ticket_loads_nothing():
    """定不出本轮要接的卡时，不得加载任何台账（否则历史规格点灌满首屏）。"""
    mod = _load_boot()
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(Path(tmp))
        problems, notes = mod.run_distill_checks(root, "")
        combined = "\n".join(problems + notes)
        assert "历史卡旧项" not in combined, (
            f"未绑定任务卡时不得加载历史台账；实际：{combined[:400]}"
        )
        assert "规格点" not in combined or "不加载任何台账" in combined, (
            f"未绑定任务卡时应明确说明不加载台账；实际：{combined[:400]}"
        )


def test_spec_scope_only_current_ticket():
    """指定本卡后，首屏加载的规格点必须只来自**本次要接的卡**。"""
    mod = _load_boot()

    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(Path(tmp))
        problems, notes = mod.run_distill_checks(root, "", "T-CUR")
        combined = "\n".join(problems + notes)
        assert "T-OLD" not in combined, (
            "首屏不得出现历史台账（T-OLD*）的规格点；"
            f"实际输出：{combined[:400]}"
        )
        assert "历史卡旧项" not in combined, (
            "首屏不得出现历史卡台账的规格点正文；"
            f"实际输出：{combined[:500]}"
        )
        # 计数必须只算本卡：fixture 里本卡 1 条，历史 6 条。
        m = re.search(r"规格点 (\d+) 条", combined)
        assert m, f"未找到规格点计数：{combined[:400]}"
        assert int(m.group(1)) == 1, (
            f"规格点计数必须只统计本卡（应为 1），实际 {m.group(1)}——说明仍在扫全目录。"
        )
        assert "本卡未回收项" in combined, (
            "本卡未回收规格点必须被加载；"
            f"实际输出：{combined[:400]}"
        )


def test_distill_spec_requires_ticket_scoping():
    """flow-distill 必须支持按 ticket 限定；不传时行为不得让调用方误用。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(Path(tmp))
        scoped = subprocess.run(
            [sys.executable, str(DISTILL), "spec", "--project", str(root),
             "--ticket", "T-CUR"],
            capture_output=True, text=True,
        )
        out = scoped.stdout
        assert "T-OLD" not in out, f"限定 T-CUR 时不得出现历史卡内容：{out[:300]}"
        assert "SPE-1" in out, f"限定 T-CUR 时应读到本卡规格点：{out[:300]}"


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
