#!/usr/bin/env python3
"""规格点回收台账 + 交接棒蒸馏校验。

两个真实缺口（2026-09-23 取证 8 个分端会话 rollout）：
1. P0/P4 会话被 Codex 自动压缩时，模型把用户消息**原样回放**成 12k~29k 字节的
   复述块当作汇报（`task_complete.last_agent_message` 就是那块）。原样摘抄既不是
   需求点也不是规格点：新会话只能重读全部历史，等于熔断白做。
2. 中断后没有销账台账，同一个需求点会被反复执行。

因此交接必须落盘 SDD 蒸馏产物：规格点(SPE) + 待办(TODO) + 逐条回收状态。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SPEC_DIR = "specs"
SPEC_LINE = re.compile(r"^\s*[-*]\s*\[([ x\-!])\]\s*(SPE-\d+)\s*\|\s*(.*?)\s*\|\s*证据：\s*(.*)$")
OK_STATES = (" ", "x", "-", "!")
SHINGLE = 32
# 主判据是「最长连续照抄」：实测 P4 真实回放块（12942 字符）的照抄比例只有 26%
# ——因为它边叙述边摘抄，比例被稀释——但最长连续照抄达 958 字符，一判即中。
# 比例只作辅助（防止「拆碎了copy」绕过）。调参时不要删掉串长这条。
MAX_COPIED_RATIO = 0.60
MAX_COPIED_RUN = 400
DISTILL_MARKERS = ("规格点", "SPE-", "待办", "TODO", "- [ ]", "- [x]")


def normalize(text: str) -> str:
    """去掉空白与标点，避免靠加空格/换行绕过照抄检测。"""
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def shingles(text: str) -> list[str]:
    if len(text) < SHINGLE:
        return [text] if text else []
    return [text[i : i + SHINGLE] for i in range(len(text) - SHINGLE + 1)]


def copied_span(handoff: str, sources: list[str]) -> tuple[float, int]:
    """返回（照抄比例, 最长连续照抄字符数）。"""
    source_pool: set[str] = set()
    for source in sources:
        source_pool.update(shingles(normalize(source)))
    parts = shingles(normalize(handoff))
    if not parts or not source_pool:
        return 0.0, 0
    hits = [part in source_pool for part in parts]
    longest = current = 0
    for hit in hits:
        current = current + 1 if hit else 0
        longest = max(longest, current)
    run_chars = longest + SHINGLE - 1 if longest else 0
    return sum(hits) / len(hits), run_chars


def load_user_messages(sessions_root: Path, thread_id: str) -> list[str]:
    """取该线程 rollout 里的用户消息原文，作为「照抄源」。"""
    import json

    matches = sorted(
        sessions_root.rglob(f"*{thread_id}*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    texts: list[str] = []
    for path in matches[:2]:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = item.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if item.get("type") != "response_item" or payload.get("type") != "message":
                continue
            if payload.get("role") != "user":
                continue
            texts.append(
                "".join(part.get("text", "") for part in (payload.get("content") or []))
            )
    return texts


def top_handoff(flow: Path) -> str:
    progress = flow / "进展.md"
    if not progress.is_file():
        return ""
    lines = progress.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(("## ", "### "))), None)
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith(("## ", "### ")):
            end = index
            break
    return "\n".join(lines[start:end])


def check_handoff(
    flow: Path, thread_id: str, sessions_root: Path, text_file: Path | None = None
) -> list[str]:
    body = text_file.read_text(encoding="utf-8", errors="replace") if text_file else top_handoff(flow)
    if not body:
        return []
    problems: list[str] = []
    if not check_handoff_markers_ok(body):
        problems.append(
            "交接棒缺少 SDD 蒸馏结构（规格点 SPE-n / 待办 TODO 清单）："
            "交接必须写「要执行的规格」，不能只写状态叙述。"
        )
    ratio, run_chars = copied_span(body, load_user_messages(sessions_root, thread_id))
    if ratio >= MAX_COPIED_RATIO or run_chars >= MAX_COPIED_RUN:
        problems.append(
            f"交接棒疑似原样照抄用户消息（照抄比例 {ratio:.0%}、最长连续 {run_chars} 字符）："
            "请蒸馏成规格点/待办，不要回放用户原话。"
        )
    return problems


def check_handoff_markers_ok(body: str) -> bool:
    """交接棒是否带 SDD 蒸馏结构（规格点 / 待办清单）。"""
    return any(marker in body for marker in DISTILL_MARKERS)


def ledger_lines(path: Path) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    entries: list[tuple[str, str, str, str]] = []
    problems: list[str] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line.startswith(("- ", "* ")):
            continue
        match = SPEC_LINE.match(raw)
        if not match:
            problems.append(f"{path.name}:{number} 行不符合台账格式：{raw.strip()[:60]}")
            continue
        state, spe, spec, evidence = match.groups()
        if spe in seen:
            problems.append(f"{path.name}:{number} 规格点编号重复：{spe}")
        seen.add(spe)
        entries.append((state, spe, spec, evidence.strip()))
    return entries, problems


def check_specs(flow: Path, ticket: str) -> tuple[list[str], list[str], list[str]]:
    """返回（问题, 回收表行, 未回收行）。"""
    specs_dir = flow / SPEC_DIR
    if not specs_dir.is_dir():
        return [], [], []
    paths = sorted(specs_dir.glob(f"{ticket}.md")) if ticket else sorted(specs_dir.glob("*.md"))
    if not paths:
        return [], [], []
    problems: list[str] = []
    table: list[str] = []
    pending: list[str] = []
    for path in paths:
        entries, issues = ledger_lines(path)
        problems.extend(issues)
        if not entries:
            problems.append(
                f"{path.name} 没有任何规格点条目：台账必须逐条写 `- [ ] SPE-1 | 规格点 | 证据：`"
            )
            continue
        for state, spe, spec, evidence in entries:
            label = {" ": "未做", "-": "进行中", "x": "已完成", "!": "阻塞"}.get(state, "未知")
            table.append(f"- [{state}] {spe} | {spec} | {label} | 证据：{evidence or '（缺）'}")
            if state == "x" and not evidence:
                problems.append(f"{spe} 标记完成但没有证据：不得假销账。")
            if state != "x":
                pending.append(f"{spe} | {spec} | {label}")
    return problems, table, pending


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=["spec", "handoff"], default="spec")
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--ticket", default="")
    parser.add_argument("--thread-id", default="")
    parser.add_argument(
        "--text-file",
        type=Path,
        default=None,
        help="校验指定文件里的交接棒文本（默认读 flow/进展.md 顶部）；用于核销被顶掉的旧交接棒",
    )
    parser.add_argument("--sessions-root", type=Path, default=Path.home() / ".codex" / "sessions")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    flow = args.project.resolve() / "flow"
    if args.mode == "handoff":
        if not args.thread_id:
            # 不能把「测不了」当成「通过」：缺 thread-id 时无法取到照抄比对源，
            # 此时必须显式告警并判失败，否则调用方会以为照抄检测跑过了。
            print("project-flow 交接棒蒸馏校验")
            print("! 缺少 --thread-id：无法取用户消息做照抄比对，交接棒不得视为通过。")
            return 1
        problems = check_handoff(flow, args.thread_id, args.sessions_root, args.text_file)
        if problems:
            print("project-flow 交接棒蒸馏校验")
            for problem in problems:
                print(f"! {problem}")
            return 1
        print("project-flow 交接棒蒸馏校验：通过（规格点结构齐备，未发现原样照抄）")
        return 0

    problems, table, pending = check_specs(flow, args.ticket)
    print("project-flow 规格点回收校验")
    if table:
        print(f"- 规格点 {len(table)} 条，未回收 {len(pending)} 条")
        for row in table[-20:]:
            print(f"  {row}")
    else:
        print("- 无规格点台账（flow/specs/<ticket>.md 尚未建立）")
    for problem in problems:
        print(f"! {problem}")
    if pending:
        print(
            "- 续跑口径：只做上面未回收的规格点；标记 [x] 的完成项不得重复执行。"
        )
    return 1 if problems else 0


def self_test() -> int:
    # 整段复述用户消息（P0/P4 的真实形态）：必须被判为原样照抄。
    replay = "用户要求作为企业 Web 端 Agent 完成这十四个薄壳页的返工并补齐缺失的四项操作，收工必须运行交付脚本并原样粘贴看板。" * 8
    ratio, run_chars = copied_span("## 交接棒\n" + replay, [replay])
    assert ratio > 0.9 and run_chars >= MAX_COPIED_RUN, (ratio, run_chars)
    # 蒸馏产物只引用个别路径/命令：不得误报。
    short = "## 交接棒\n- 规格点 SPE-1 | 修复登录 | 证据：pytest exit 0"
    ratio2, run2 = copied_span(short, ["完全无关的用户消息内容" * 20])
    assert ratio2 < 0.2 and run2 == 0, (ratio2, run2)
    assert not check_handoff_markers_ok("## 交接棒\n- 现状：在做，还没好")
    assert check_handoff_markers_ok("## 交接棒\n- [ ] SPE-1 | 修复登录 | 证据：")
    match = SPEC_LINE.match("- [x] SPE-1 | 规格点描述 | 证据：pytest exit 0")
    assert match and match.group(1) == "x" and match.group(2) == "SPE-1", match
    assert not SPEC_LINE.match("- [x] SPE-1 | 缺证据"), "缺证据的行必须被拒"
    print("PASS: flow-distill detects verbatim replay and validates the spec ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
