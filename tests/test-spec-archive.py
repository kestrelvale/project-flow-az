#!/usr/bin/env python3
"""PFP-SPEC-ACCUMULATION-20260928：台账必须随任务卡一起归档。

缺陷（2026-09-28 真机复现）：
    flow-gc.py 的 `HISTORY_DIRS` 漏了 `specs`，且 task_archive 只搬任务卡。
    结果：12 张台账里 9 张的主卡早已归档、台账却原地滞留在 flow/specs/
    （且全部 0 条未回收）。这些孤儿台账被下轮会话全量加载。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GC = REPO / "scripts" / "flow-gc.py"


def make_project(root: Path, ticket: str) -> Path:
    (root / "flow" / "tasks").mkdir(parents=True)
    (root / "flow" / "specs").mkdir(parents=True)
    (root / "flow" / "plan.md").write_text(
        f"## 🎯 当前聚焦待办 (P0)\n- [-] {ticket} 待验收\n", encoding="utf-8"
    )
    (root / "flow" / "tasks" / f"{ticket}.md").write_text(
        f"ticket_id: {ticket}\nobjective: 演示\nmode: execute\n", encoding="utf-8"
    )
    (root / "flow" / "specs" / f"{ticket}.md").write_text(
        f"# 台账 · {ticket}\n- [x] SPE-1 | 已完成项 | 已完成 | 证据：x\n",
        encoding="utf-8",
    )
    return root


def test_ledger_moves_with_card():
    """归档任务卡时，规格点台账必须同步移入 flow/history/specs/。"""
    ticket = "PFP-DEMO-20260928"
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(Path(tmp), ticket)
        result = subprocess.run(
            [sys.executable, str(GC), str(root), "--apply",
             "--task-archive", ticket, "--reason", "user_accepted",
             "--evidence", "测试"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"归档失败：{result.stdout}{result.stderr}"
        assert not (root / "flow" / "specs" / f"{ticket}.md").exists(), (
            "归档后台账不得留在 flow/specs/ —— 否则会累积成孤儿台账，被下轮全量加载"
        )
        assert (root / "flow" / "history" / "specs" / f"{ticket}.md").is_file(), (
            "归档后台账应出现在 flow/history/specs/"
        )


def test_archive_without_ledger_still_works():
    """没有台账的卡照常归档，不得因为缺台账而失败。"""
    ticket = "PFP-NOLEDGER-20260928"
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(Path(tmp), ticket)
        (root / "flow" / "specs" / f"{ticket}.md").unlink()
        result = subprocess.run(
            [sys.executable, str(GC), str(root), "--apply",
             "--task-archive", ticket, "--reason", "user_accepted",
             "--evidence", "测试"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"缺台账不应导致归档失败：{result.stdout}{result.stderr}"
        assert (root / "flow" / "history" / "tasks" / f"{ticket}.md").is_file()


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
