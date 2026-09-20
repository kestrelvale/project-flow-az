#!/usr/bin/env python3
"""四区归档结构最小测试：同步补齐目录并迁移旧混放目标。"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNC = ROOT / "scripts" / "sync-project.py"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        flow = target / "flow"
        (flow / "history").mkdir(parents=True)
        (flow / "trash" / "verification-gc" / "old").mkdir(parents=True)
        (flow / "history" / "进展_archive.md").write_text("old", encoding="utf-8")
        (flow / "trash" / "verification-gc" / "old" / "probe.log").write_text("x", encoding="utf-8")

        subprocess.run(
            [sys.executable, str(SYNC), str(ROOT), str(target)],
            text=True,
            capture_output=True,
            check=True,
        )

        for relative in (
            "flow/history/plans",
            "flow/history/tasks",
            "flow/history/progress",
            "flow/trash/deprecated",
            "flow/trash/verification",
            "flow/gc/receipts",
        ):
            assert (target / relative).is_dir(), relative
        assert (flow / "history" / "progress" / "进展_archive.md").is_file()
        assert (flow / "trash" / "verification" / "legacy-verification-gc" / "old" / "probe.log").is_file()
    print("PASS: sync-project creates four-zone archive layout and migrates legacy paths")


if __name__ == "__main__":
    main()
