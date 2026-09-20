#!/usr/bin/env python3
"""最小行为测试：旧表格格式中的完成项必须暴露为遗留问题。"""
from __future__ import annotations

import tempfile
import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit-flow.py"
BOOT = SCRIPT.parent / "flow-boot.py"
EXPECTED_VERSION = (SCRIPT.parent.parent / "VERSION").read_text(encoding="utf-8").strip()
SPEC = importlib.util.spec_from_file_location("audit_flow", SCRIPT)
assert SPEC and SPEC.loader
AUDIT_FLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT_FLOW)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow = root / "flow"
        flow.mkdir()
        (flow / "plan.md").write_text(
            "| 任务 | 状态 |\n|---|---|\n| A | ✅ 已完成 |\n| B | 🔴 当前任务 |\n",
            encoding="utf-8",
        )
        for name in ("进展.md", "charter.md", "decisions.md", "踩坑记录.md"):
            (flow / name).write_text("", encoding="utf-8")
        report = AUDIT_FLOW.audit(root)
        assert report["status"] == "error", report
        assert any("plan.md:3" in error for error in report["errors"]), report
        assert any(task["state"] == " " for task in report["tasks"]), report

        (flow / "verification-tmp").mkdir()
        (flow / "verification-tmp" / "probe.log").write_text("x", encoding="utf-8")
        (root / "tmp").mkdir()
        (root / "tmp" / "keep.txt").write_text("keep", encoding="utf-8")
        agents = root / "AGENTS.md"
        agents.write_text("# AGENTS\n\nkeep me\n", encoding="utf-8")
        boot = subprocess.run(
            [sys.executable, str(BOOT), str(root)],
            text=True,
            capture_output=True,
        )
        assert "已热同步" in boot.stdout, boot
        assert "plan.md:3" in boot.stdout, boot
        assert "keep me" in agents.read_text(encoding="utf-8"), agents.read_text(encoding="utf-8")
        assert (flow / "规范" / "VERSION").read_text(encoding="utf-8").strip() == EXPECTED_VERSION
        template = flow / "tasks" / "TEMPLATE.md"
        assert template.is_file(), template
        assert "ticket_id:" in template.read_text(encoding="utf-8"), template.read_text(encoding="utf-8")
        template.write_text("旧模板", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(BOOT), str(root)],
            text=True,
            capture_output=True,
        )
        assert "ticket_id:" in template.read_text(encoding="utf-8"), template.read_text(encoding="utf-8")
        assert not (flow / "verification-tmp").exists()
        assert (flow / "trash" / "verification").is_dir()
        assert list((flow / "gc" / "receipts").glob("*.json")), "GC 必须留下回执"
        assert (root / "tmp" / "keep.txt").exists()
    print("PASS: audit-flow exposes completed legacy table rows")


if __name__ == "__main__":
    main()
