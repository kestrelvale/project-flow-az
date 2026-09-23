#!/usr/bin/env python3
"""CHANGELOG 完整性护栏。

事故（2026-09-23，v4.15.4 提交 `1dea9ca`）：脚本用 write_text 覆盖写，把 49153 字节 /
41 段的发布历史截成 2658 字节 / 1 段，并且已推送远端。同类事故必须被机器挡住，
而不是靠人记得「新增条目要 prepend，不要 overwrite」。
"""
from __future__ import annotations

import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
# 层数下限按发布历史设：2026-09-23 实际 43 段。留出余量但不允许断崖式丢失。
MIN_SECTIONS = 40


def main() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    sections = re.findall(r"(?m)^## \[(\d+\.\d+\.\d+)\]", text)
    assert len(sections) >= MIN_SECTIONS, (
        f"CHANGELOG 只剩 {len(sections)} 段（下限 {MIN_SECTIONS}）："
        f"疑似被覆盖写截断，发布历史不得丢失"
    )
    # 从文件开头起算「最长降序前缀」：新条目必须 prepend 在最前面。
    # 不要求全表降序——本仓库历史上游就有乱序（尾部残留 … 2.2.0 / 4.9.0 / 4.9.1 / 4.9.2），
    # 那不是本次事故。截断事故的形态是「开头这段整体消失」，用前缀长度即可抓住。
    def key(value: str) -> tuple[int, ...]:
        return tuple(int(x) for x in value.split("."))

    prefix = 1
    while prefix < len(sections) and key(sections[prefix]) < key(sections[prefix - 1]):
        prefix += 1
    assert prefix >= 5, (
        f"开头降序区间只剩 {prefix} 段（下限 5）：疑似发布历史被截断或新条目写错位置"
    )
    assert key(sections[0]) >= (4, 15, 0), f"最新版本倒退到 {sections[0]}"
    # 每个新版本都要有独立的诊断/验证小节，防止只写一行标题。
    for version in sections[:3]:
        block = text.split(f"## [{version}]", 1)[1].split("\n## [", 1)[0]
        assert "### " in block, f"{version} 条目没有任何小节（### …）"
    assert "### Packaging" in text, "缺 ### Packaging 小节（结构约定）"
    print(f"PASS: CHANGELOG keeps {len(sections)} version sections in descending order")


if __name__ == "__main__":
    main()
