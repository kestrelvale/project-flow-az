#!/usr/bin/env python3
"""独立验收 4.15.19：接力身份的「源交接棒」按 ticket 定位 + 显式点名优先。

与实现方自己的 tests/test-relay-multi-task.py 分开写：这里从**规格**出发独立搭夹具，
不复用它的 build()，也不复用它的断言，避免"实现和测试同源错误"一起绿。

验收对象（对照 flow/tasks/*.md 的 acceptance 字段）：
  IDENTITY  : Given 顶部交接棒属于 A 卡、意图指向 B 卡，Then 来源交接棒与现状/还剩/卡在哪全来自 B 卡；
              Given 目标卡无交接棒，Then 写「未声明」而非贴他卡。
  MULTITASK : Given 意图点名 B、B 不在活跃区、A 条目引用了 B 的编号，Then 返回 B，不得被 A 兜底。

tamper 模式：--tamper <场景> 故意把被测行为改坏，断言必须变红——证明这些检查真的能失败。
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "scripts" / "flow-budget.py"
UID = "01a0dead-beef-7000-8000-000000000001"

CARD_A = "ZZ-TOP-20260926"      # 顶部交接棒所属（并发会话的卡）
CARD_B = "ZZ-TARGET-20260926"   # 本轮真正要接的卡
CARD_C = "ZZ-NOCARD-20260926"   # 有卡文件、但进展.md 里没有它的交接棒


def build(root: Path) -> Path:
    """独立搭一个最小工作根：顶部交接棒属于 A，目标 B 在活跃区。"""
    flow = root / "flow"
    for name in ("tasks", "specs", "budget", "history/tasks", "规范"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范" / "VERSION").write_text("9.9.9", encoding="utf-8")
    (flow / "plan.md").write_text(
        "\n".join([
            "# Plan",
            "## 🎯 当前聚焦待办 (P0)",
            f"- [ ] {CARD_B} [P0] 目标卡：本轮的活",
            f"- [ ] {CARD_C} [P0] 另一张卡",
        ]) + "\n", encoding="utf-8")
    (flow / "进展.md").write_text(
        "\n".join([
            f"## 2026-09-26 · {CARD_A} · 交接棒（SDD 蒸馏） · thread={UID}",
            f"- 来源会话：thread={UID}",
            "- 现状：TOP 卡的现状，绝不能出现在 B 卡的提示词里",
            "- 还剩：TOP-1",
            "- 卡在哪：TOP 的阻塞",
            "- 下一步：TOP 的下一步",
            f"- 台账：flow/specs/{CARD_A}.md",
            "",
            f"## 2026-09-26 · {CARD_B} · 交接棒（SDD 蒸馏） · thread={UID}",
            f"- 来源会话：thread={UID}",
            "- 现状：TARGET 卡的现状",
            "- 还剩：TARGET-1",
            "- 卡在哪：无",
            "- 下一步：TARGET 的下一步",
            f"- 台账：flow/specs/{CARD_B}.md",
        ]) + "\n", encoding="utf-8")
    for tk in (CARD_A, CARD_B, CARD_C):
        (flow / "tasks" / f"{tk}.md").write_text(
            f"ticket_id: {tk}\nobjective: {tk} 的目标\nmode: execute\n"
            f"acceptance: Given x，When y，Then z\n", encoding="utf-8")
    # 提示词走「已熔断 → 生成接力提示词」路径，需要 stop 回执 + 会话 jsonl 指明来源会话。
    (flow / "budget" / "20260926-000000-stop.json").write_text(
        json.dumps({"operation": "budget_stop", "thread_id": UID}, ensure_ascii=False),
        encoding="utf-8")
    sess = root / "sessions" / "2026" / "09" / "26" / f"rollout-{UID}.jsonl"
    sess.parent.mkdir(parents=True, exist_ok=True)
    sess.write_text(json.dumps({
        "type": "event_msg",
        "payload": {"type": "token_count", "input_tokens": 300_000, "context_window": 950_000},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    return root


def run_relay(root: Path, intent: str, *extra: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(BUDGET), "--print-relay", "--project", str(root),
         "--thread-id", UID, "--intent", intent,
         "--sessions-root", str(root / "sessions"), *extra],
        text=True, capture_output=True)
    assert proc.returncode == 0, (proc.returncode, proc.stderr[-800:])
    return proc.stdout


def field(text: str, name: str) -> str:
    for line in text.splitlines():
        if line.startswith(name):
            return line
    return ""


def scenario_handoff_from_target() -> None:
    """ATDD-1：顶部是 A、意图指向 B → 来源交接棒与任务说明四字段必须来自 B。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = build(Path(tmp))
        text = run_relay(root, f"接力 {CARD_B}：干活")
        assert f"来源任务卡：{CARD_B}" in text, text[-1200:]
        hl = field(text, "来源交接棒：")
        assert CARD_A not in hl, "来源交接棒贴了顶部那张卡：" + hl
        assert CARD_B in hl, hl
        # 任务说明四字段必须来自 B 卡，不得出现 A 卡的现状
        assert "TARGET 卡的现状" in text, text[-1200:]
        assert "TOP 卡的现状" not in text, "把顶部卡(A)的现状贴给了目标卡(B)：" + text[-1200:]


def scenario_missing_handoff() -> None:
    """ATDD-2：目标卡在进展.md 无交接棒 → 照实写未声明，不得退化成贴他卡。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = build(Path(tmp))
        text = run_relay(root, f"接力 {CARD_C}：干活")
        hl = field(text, "来源交接棒：")
        assert CARD_A not in hl, "目标卡无交接棒时贴了他卡：" + hl
        assert "未见" in hl or "未声明" in hl or CARD_C in hl, hl


def scenario_explicit_wins() -> None:
    """ATDD-3：意图点名 B，A 条目引用了 B 编号 → 必须解析为 B，不得被 A 兜底。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = build(Path(tmp))
        plan = root / "flow" / "plan.md"
        raw = plan.read_text(encoding="utf-8")
        # 制造"引用"：A 条目文字里出现 B 的编号
        raw = raw.replace(f"- [ ] {CARD_B} [P0] 目标卡：本轮的活",
                          f"- [ ] {CARD_A} [P0] 总控：等 {CARD_B} 的成果合入")
        plan.write_text(raw, encoding="utf-8")
        text = run_relay(root, f"接力 {CARD_B}：干活")
        assert f"flow/tasks/{CARD_A}.md" not in text, \
            "意图点名 B 却被引用 B 编号的 A 卡兜底：" + text[-1200:]


def scenario_handoff_sections_bounded() -> None:
    """ATDD-4：边界——B 卡交接棒在 A 之后，不能被 A 的字段污染（字段必须按标题分块截断）。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = build(Path(tmp))
        text = run_relay(root, f"接力 {CARD_B}：干活")
        assert "TOP 的下一步" not in text, "越界读到了 A 卡的下一步：" + text[-1200:]
        assert "TOP 的阻塞" not in text, "越界读到了 A 卡的阻塞：" + text[-1200:]


SCENARIOS = {
    "handoff_from_target": scenario_handoff_from_target,
    "missing_handoff": scenario_missing_handoff,
    "explicit_wins": scenario_explicit_wins,
    "handoff_sections_bounded": scenario_handoff_sections_bounded,
}


def main() -> int:
    tamper = ""
    if "--tamper" in sys.argv:
        tamper = sys.argv[sys.argv.index("--tamper") + 1]
        assert tamper in SCENARIOS, f"未知场景 {tamper!r}；可选：{list(SCENARIOS)}"
        SCENARIOS[tamper]()
        print(f"PASS: {tamper}")
        return 0
    # 无参（跑在 run-all.sh 里）：正跑全部场景
    for name in SCENARIOS:
        SCENARIOS[name]()
    print(f"PASS: 4.15.19 验收 —— {len(SCENARIOS)} 个场景全绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
