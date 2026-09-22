#!/usr/bin/env python3
"""进展日志分页回归：`### ` 写法与大体积日志都必须被滚动归档。

真实故障：o2o 的进展.md 用 `### ` 写了 40 条共 86KB，旧实现只认 `## `，
结果一条都没滚动，每次开工全量灌进上下文，会话必然中途熔断。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "flow-gc.py"
spec = importlib.util.spec_from_file_location("flow_gc", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_progress(flow: Path, count: int, filler: int = 400, marker: str = "### ") -> None:
    lines = ["# 进展日志\n\n"]
    for index in range(count):
        lines.append(f"{marker}2026-09-{(index % 28) + 1:02d} (【任务{index}】)\n")
        lines.append("- 做了什么: " + "内容" * filler + "\n")
    (flow / "进展.md").write_text("".join(lines), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        flow = Path(tmp) / "flow"
        (flow / "history" / "progress").mkdir(parents=True)

        # `### ` 写法也必须被识别：这正是 o2o 漏滚动的直接原因。
        write_progress(flow, 12, marker="### ")
        messages = module._rotate_progress(flow, apply=True)
        assert messages, "### 写法的日志未被滚动"
        remaining = (flow / "进展.md").read_text(encoding="utf-8")
        assert remaining.count("### ") <= module.MAX_PROGRESS_ENTRIES, remaining.count("### ")
        archived = list((flow / "history" / "progress").glob("*.md"))
        assert archived, "滚动后未生成历史文件"

    with tempfile.TemporaryDirectory() as tmp:
        flow = Path(tmp) / "flow"
        (flow / "history" / "progress").mkdir(parents=True)
        # 条数未超上限但总体积超限时，同样必须滚动，只留最近一条。
        write_progress(flow, 6, filler=1200, marker="## ")
        before = len((flow / "进展.md").read_text(encoding="utf-8"))
        assert before > module.MAX_PROGRESS_BYTES, before
        messages = module._rotate_progress(flow, apply=True)
        assert messages, "大体积日志未被滚动"
        remaining = (flow / "进展.md").read_text(encoding="utf-8")
        # 只保留“能塞进保留区间”的最近若干条，且必须显著瘦身。
        assert 1 <= remaining.count("## ") <= module.MAX_PROGRESS_ENTRIES, remaining.count("## ")
        # 保留区间是近似目标：按条目边界切，单条可能略大于 KEEP 阈值。
        assert len(remaining) < module.MAX_PROGRESS_BYTES, len(remaining)
        assert len(remaining) < before, (before, len(remaining))

    print("PASS: flow-gc rotates both '###' logs and oversized logs")


if __name__ == "__main__":
    main()
