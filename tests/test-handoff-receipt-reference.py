#!/usr/bin/env python3
"""熔断核销的参照回执必须是「开工前」那条。

缺陷（2026-09-23 实测）：flow-boot 先跑 flow-budget 写出一条新回执，该回执的
handoff_head 捕获的是「此刻的顶部标题」，随后 render_stop_reports 又拿这条**刚写的**
回执去比「顶部标题有没有变」——两者必然相等，于是柔性阻塞永远核销不掉。
本案用例 3/4 锁死修复后的语义。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "flow-boot.py"

SPEC = importlib.util.spec_from_file_location("flow_boot_under_test", BOOT)
assert SPEC and SPEC.loader
fb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fb)

OLD = "## 2026-09-22 · 旧交接棒 · T1"
NEW = "## 2026-09-23 · T1 · 交接棒（SDD 蒸馏）"
HANDOFF = "\n".join(
    [
        NEW,
        "- 规格点 SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
        "- 还剩：SPE-2",
        "- 卡在哪：无",
        "- 下一步：开新会话按未回收规格点继续",
        "",
    ]
)


def build(top: str, heads: list[str]) -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    flow = root / "flow"
    for name in ("tasks", "history", "trash", "规范", "budget"):
        (flow / name).mkdir(parents=True)
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "# Plan\n## 当前聚焦待办 (P0)\n- [ ] T1 [登录状态修复] 修正登录失效\n",
        encoding="utf-8",
    )
    for name in ("charter.md", "decisions.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    (flow / "进展.md").write_text(top, encoding="utf-8")
    for index, head in enumerate(heads):
        (flow / "budget" / f"20260923-12{index:02d}00-stop.json").write_text(
            json.dumps(
                {
                    "operation": "budget_stop",
                    "input_tokens": 300_000,
                    "rounds": 23,
                    "tool_calls": 160,
                    "reasons": ["工具调用 160 >= 160"],
                    "handoff_head": head,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return root, flow


def check(label: str, cond: bool, extra: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f" :: {extra}"))
    if not cond:
        raise AssertionError(label)


def main() -> None:
    # 用例1：参照=旧标题、顶部=新交接棒 → 已交接（核销）
    root1, flow1 = build(HANDOFF, [OLD])
    ref1 = fb.latest_receipt_path(flow1)
    pending1, _ = fb.read_pending_stop(flow1, "t", ref1)
    check("参照为开工前回执（旧标题）且顶部已换新交接棒 → 核销", pending1 is None, str(pending1))

    # 用例2：同场景但缺省参数（仍取最新回执）→ 行为一致，向后兼容
    pending2, _ = fb.read_pending_stop(flow1, "t")
    check("缺省参数仍取最新回执且结论一致", pending2 is None, str(pending2))

    # 用例3：新增一条「开工这次刚写的」回执，其 handoff_head = 当前顶部标题 → 模拟旧缺陷现场。
    #        参照取开工前那条 → 仍应核销（这是修复的核心）
    root3, flow3 = build(HANDOFF, [OLD, NEW])
    ref3 = fb.latest_receipt_path(flow3)
    check(
        "开工前回执是最新那条之前的一条（快照语义）",
        ref3 is not None and ref3.name == "20260923-120000-stop.json",
        str(ref3),
    )
    pending3, _ = fb.read_pending_stop(flow3, "t", ref3)
    check("用开工前回执作参照 → 不会被本次新写的回执自己卡住", pending3 is None, str(pending3))

    # 用例4：门禁仍有牙齿——顶部标题与参照回执相同（没写新交接棒）→ 必须报未交接
    root4, flow4 = build(HANDOFF, [NEW])
    ref4 = fb.latest_receipt_path(flow4)
    pending4, _ = fb.read_pending_stop(flow4, "t", ref4)
    check("顶部标题未变（未写新交接棒）→ 仍报未交接", pending4 is not None, str(pending4))

    # 用例5（实测事故 2026-09-23 thread 01a0c24b）：多会话并发写同一个项目时，
    # 参照回执必须**优先取属于本会话**的那条。旧实现机械取「倒数第二条」，
    # 恰好取到别的会话的回执 → 来源会话不匹配 → 本会话自己写的合法交接棒永远核销不掉，
    # 表现为「反复 STOP、反复柔性阻塞、走不出去」。
    uid = "01a0c24b-06d4-7ad0-8253-92d1e8a6b667"
    other = "01a0c297-b8e5-7561-9014-570c11a5499e"
    top5 = HANDOFF.replace(NEW, f"{NEW} · thread={uid}")
    root5, flow5 = build(top5, [OLD, OLD, f"{NEW} · thread={uid}"])
    for name, tid in (
        ("20260923-120000-stop.json", uid),      # 本会话（head=旧）
        ("20260923-120100-stop.json", other),    # 别的会话（head=旧）
        ("20260923-120200-stop.json", uid),      # 本会话刚写（head=当前顶部）
    ):
        path = flow5 / "budget" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data["thread_id"] = tid
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    ref5 = fb.latest_receipt_path(flow5, uid)
    check(
        "参照优先取本会话回执（而非别人的）",
        ref5 is not None and ref5.name == "20260923-120000-stop.json",
        str(ref5),
    )
    pending5, _ = fb.read_pending_stop(flow5, uid, ref5)
    check("本会话合法交接棒 → 核销（不再被别人的回执卡住）", pending5 is None, str(pending5))

    for root in (root1, root3, root4, root5):
        for child in sorted(root.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
    print("PASS: 熔断核销以「开工前回执」为参照，且未交接仍被拦住")


if __name__ == "__main__":
    main()
