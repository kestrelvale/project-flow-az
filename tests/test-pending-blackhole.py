#!/usr/bin/env python3
"""PFP-PENDING-BLACKHOLE-20260927：`[-]` 不得变黑洞。

缺陷（2026-09-27 真机复现）：
    6 张卡堆在 `[-]`、`[ ]` 为空 → 每轮开工「本轮尚未登记原子任务」→ 只能去改框架；
    改完又新增 `[-]` 卡 → 下轮活跃区又被占满。**这是「改了几十遍没变化」的机制本身。**

修复后：`[ ]` 为空且 `[-]` 达到阈值时，必须计入路由阻塞（先清账才能开新活）。
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOT = REPO / "scripts" / "flow-boot.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_blocked_when_no_active_and_pending_pile_up():
    """`[ ]` 为空 + `[-]` 达阈值 → 必须判为阻塞。"""
    boot = load(BOOT, "flow_boot")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "flow").mkdir(parents=True)
        pending = "".join(f"- [-] PFP-DEMO-{i} 待验收卡\n" for i in range(1, 7))
        (root / "flow" / "plan.md").write_text(
            f"## 🎯 当前聚焦待办 (P0)\n- [✓] 已完成的旧活\n\n"
            f"## ⏳ 待人工验收 (Pending Verification)\n{pending}",
            encoding="utf-8",
        )
        active = boot.read_active_tasks(root / "flow" / "plan.md")
        assert active == [], f"本夹具应无 `[ ]` 活跃任务，实际 {active}"
        blocked, reason = boot.pending_blackhole(root)
        assert blocked, "`[ ]` 为空而 `[-]` 堆了 6 张，必须判为阻塞；实际未阻塞"
        assert "待验收" in reason, f"阻塞原因应说明 `[-]` 堆积，实际 {reason!r}"


def test_not_blocked_when_active_focus_exists():
    """有 `[ ]` 活跃焦点时，`[-]` 再多也不该阻塞（否则永远开不了新活）。"""
    boot = load(BOOT, "flow_boot")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "flow").mkdir(parents=True)
        pending = "".join(f"- [-] PFP-DEMO-{i} 待验收卡\n" for i in range(1, 9))
        (root / "flow" / "plan.md").write_text(
            f"## 🎯 当前聚焦待办 (P0)\n- [ ] PFP-NEW-1 本轮要做的活\n\n"
            f"## ⏳ 待人工验收 (Pending Verification)\n{pending}",
            encoding="utf-8",
        )
        blocked, _ = boot.pending_blackhole(root)
        assert not blocked, "存在 `[ ]` 活跃焦点时不得因为 `[-]` 堆积而阻塞"


def test_not_blocked_when_pending_below_threshold():
    """`[-]` 未达阈值不阻塞（避免刚交付一张卡就被拦）。"""
    boot = load(BOOT, "flow_boot")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "flow").mkdir(parents=True)
        (root / "flow" / "plan.md").write_text(
            "## 🎯 当前聚焦待办 (P0)\n- [✓] 已完成\n\n"
            "## ⏳ 待人工验收 (Pending Verification)\n- [-] PFP-DEMO-1 单张待验收\n",
            encoding="utf-8",
        )
        blocked, _ = boot.pending_blackhole(root)
        assert not blocked, "只堆 1 张待验收卡不该阻塞"


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
