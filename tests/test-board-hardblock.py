#!/usr/bin/env python3
"""PFP-BOARD-HARDBLOCK-20260927：漏贴看板从「提示」升为「硬阻塞」。

缺陷（2026-09-27）：`board_visible()` 已修好（能认出真交付、挡掉空承诺），
但「上轮回复缺看板」只在路由里提一句，可被忽略 → 脚本跑了、回执落盘、**回复里 0 次看板**。
修复后：漏贴看板必须阻断本轮认领（先补看板才能开工）；「不可判定」仍与「确定没贴」分开。
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOT = REPO / "scripts" / "flow-boot.py"


def test_variable_is_not_a_thin_alias():
    """源码级断言：漏贴看板必须进入「阻断认领」的条件里，而不是只 append 到提示列表。"""
    src = BOOT.read_text(encoding="utf-8")
    assert "board_blocker" in src, "必须存在独立的 board_blocker 标记"
    claim_block = src.split("claim_reports = (", 1)[1].split(")", 1)[0]
    assert "board_blocker" in claim_block, (
        "漏贴看板必须出现在阻断认领的条件里；仅在 handoff_problems 里 append 会被忽略"
    )


def test_hardblock_message_present_in_source():
    """硬阻塞文案必须存在，且与「无法判定」区分。"""
    src = BOOT.read_text(encoding="utf-8")
    assert "【硬阻塞】上轮漏贴看板" in src, "必须给出明确的硬阻塞文案"
    assert "上轮回复无法判定" in src, "「无法判定」必须仍与「确定没贴」分开处理"


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
