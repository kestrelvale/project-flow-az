#!/usr/bin/env python3
"""收工看板/汇报必须真实、完整、可被点名：修渲染矛盾与截断，并对「漏贴看板」加机检。

现场（2026-09-24/25，zhengjie-hrm）：
  1) `flow-deliver.py` 归档分区把 plan.md 的占位文字原样带出
     → 看板写「- 无（flow/history/tasks/ 已归档 82 张任务卡）」，前半句是「无」、
       后半句说 82 张，用户读到「看板宕机了」；
  2) 决策分区把 decisions.md 里多行条目的续行当独立条目输出
     → 出现半截 `- 决策:` / ``- `resolve_`` 这种残句；
  3) 会话漏贴看板没有任何机检：`flow-boot.py` 只查「查无交付回执」，
     不查「回执有、但回复里没贴看板」，于是漏贴无声无息。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELIVER = ROOT / "scripts" / "flow-deliver.py"
BUDGET = ROOT / "scripts" / "flow-budget.py"
BOOT = ROOT / "scripts" / "flow-boot.py"
UID = "01a0cf2d-89f3-7ae1-a981-51662657ac2e"
TICKET = "T1-BOARD-20260925"


def build(root: Path) -> tuple[Path, Path]:
    flow = root / "flow"
    for name in ("tasks", "specs", "budget", "deliveries", "gc/receipts", "history/tasks", "规范"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "\n".join(
            [
                "# Plan",
                "## 🎯 当前聚焦待办 (P0)",
                f"- [ ] {TICKET} [P0] 看板渲染修复",
                "## ⏳ 待人工验收 (Pending Verification)",
                "- 无",
                "## 📦 已完结归档 (Archived in flow/history/)",
                "- 无（本条在验收通过后移入 `flow/history/tasks/`）",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for name in ("charter.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    # 决策流水：第一条是多行条目（续行不含标记），第二条正常。
    (flow / "decisions.md").write_text(
        "\n".join(
            [
                "# decisions",
                "- [⚡ 自动决策] 统一登录夹具：",
                "  `resolve_feedback` MCP 工具与 `/api/feedback/resolve` 自适应回写。",
                "- [⚠️ 人工决策门] 订单状态冻结为 50/60/70。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    # 历史归档 3 张：必须走 flow-gc.py --task-archive（否则缺 JSON 回执，flow-boot 会拦）
    for index in range(3):
        ticket = f"OLD-{index}"
        (flow / "tasks" / f"{ticket}.md").write_text(
            f"ticket_id: {ticket}\nmode: execute\n", encoding="utf-8"
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "flow-gc.py"),
                str(root),
                "--task-archive",
                ticket,
                "--reason",
                "user_accepted",
                "--evidence",
                "fixture：看板归档计数用",
                "--apply",
            ],
            text=True,
            capture_output=True,
        )
    (flow / "tasks" / f"{TICKET}.md").write_text(
        "\n".join(
            [
                f"ticket_id: {TICKET}",
                "objective: 看板渲染修复",
                "mode: execute",
                "method: SDD,TDD,ATDD,BDD",
                "scope: 输入=x；输出=y；边界=z",
                "write_whitelist: scripts/flow-deliver.py",
                "verify_command: python3 tests/test-report-visibility.py",
                "acceptance: Given x，When y，Then z",
                f"spec_ledger: flow/specs/{TICKET}.md",
            ]
        ),
        encoding="utf-8",
    )
    (flow / "specs" / f"{TICKET}.md").write_text(
        "- [x] SPE-1 | 看板 | 证据：tests/test-report-visibility.py\n", encoding="utf-8"
    )
    (flow / "进展.md").write_text(
        f"## 2026-09-25 · {TICKET} · 交接棒（SDD 蒸馏） · thread={UID}\n"
        "- 来源会话：thread=" + UID + "\n"
        "- 规格点(SPE)：SPE-1\n- 待办(TODO)：- [x] SPE-1\n- 现状：x\n- 还剩：无\n"
        "- 卡在哪：无\n- 下一步：x\n"
        f"- 台账：flow/specs/{TICKET}.md\n",
        encoding="utf-8",
    )
    sessions = root / "sessions" / "2026" / "09" / "25"
    sessions.mkdir(parents=True)
    return flow, sessions


_SESSION_CLOCK = [0]


def write_session(path: Path, reply: str) -> None:
    # 必须写 `task_complete.last_agent_message`：机检（relay/board）都基于它。
    # 用递增 mtime 保证「最新」判定稳定：多个 rollout 在同一秒写入时，
    # `find_session_files` 的 mtime 排序会并列，读到的文件不确定。
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {"type": "task_complete", "last_agent_message": reply},
            },
            ensure_ascii=False,
        )
        + "\n"
        + json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": f"{path.stem}-turn-0",
                    "model_context_window": 950_000,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _SESSION_CLOCK[0] += 1
    stamp = 1_700_000_000 + _SESSION_CLOCK[0] * 60
    os.utime(path, (stamp, stamp))


def deliver(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(DELIVER),
            str(root / "flow" / "tasks" / f"{TICKET}.md"),
            "--changed",
            "x",
            "--evidence",
            "python3 tests/test-report-visibility.py Exit 0",
            "--what",
            "w",
            "--why",
            "y",
            "--understanding",
            "u",
            "--outputs",
            "o",
            "--next-step",
            "n",
        ],
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow, sessions = build(root)

        # SPE-1：归档分区必须给真实计数，不能输出与事实矛盾的「- 无」。
        board = deliver(root)
        assert board.returncode == 0, (board.returncode, board.stderr)
        text = board.stdout
        assert "## 📦 已完结归档 (Archived in flow/history/)" in text, text[:800]
        archived_section = text.split("## 📦 已完结归档 (Archived in flow/history/)", 1)[1].split(
            "## 💡", 1
        )[0]
        assert "已归档 3 张" in archived_section, archived_section
        assert "OLD-0" in archived_section, archived_section
        assert archived_section.strip().splitlines()[0].strip() != "- 无", archived_section

        # SPE-2：决策分区只输出完整条目，不得留半截续行。
        decisions = text.split("## 💡 本轮决策记录 (Decisions)", 1)[1]
        for line in decisions.splitlines():
            if not line.strip():
                continue
            assert not line.strip().startswith("`resolve_"), decisions
            assert line.strip() != "- [⚡ 自动决策] 统一登录夹具：", decisions
        assert "订单状态冻结" in decisions, decisions

        # SPE-3：上一轮回复漏贴看板 → 下一轮开工必须点名。
        write_session(sessions / f"rollout-2026-09-25T10-00-00-{UID}.jsonl", "本轮只写了一句结论，没有贴看板。")
        missing = subprocess.run(
            [
                sys.executable,
                str(BUDGET),
                "--project",
                str(root),
                "--thread-id",
                UID,
                "--intent",
                f"{TICKET} 继续",
                "--sessions-root",
                str(root / "sessions"),
                "--read-only",
            ],
            text=True,
            capture_output=True,
        )
        assert "上轮回复缺失任务看板" in missing.stdout, missing.stdout[-1200:]

        boot = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                f"{TICKET} 继续",
                "--thread-id",
                UID,
                "--sessions-root",
                str(root / "sessions"),
            ],
            text=True,
            capture_output=True,
        )
        assert "上轮回复缺失任务看板" in boot.stdout, boot.stdout[-1500:]

        # 反向：贴了看板的回复不得被点名。
        write_session(
            sessions / f"rollout-2026-09-25T10-00-00-{UID}.jsonl",
            "### 📊 任务状态看板\n\n"
            "## 🎯 当前聚焦待办 (P0)\n- 无\n\n"
            "## ⏳ 待人工验收 (Pending Verification)\n- 无\n\n"
            "## 📦 已完结归档 (Archived in flow/history/)\n- 无\n\n"
            "## 💡 本轮决策记录 (Decisions)\n- 无\n",
        )
        ok = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                f"{TICKET} 继续",
                "--thread-id",
                UID,
                "--sessions-root",
                str(root / "sessions"),
            ],
            text=True,
            capture_output=True,
        )
        assert "上轮回复缺失任务看板" not in ok.stdout, ok.stdout[-1500:]
        # SPE-5（2026-09-26）：机检不得把模型草稿当对外回复。
        # 现场：总控会话的 task_complete.last_agent_message 是 17K~33K 的
        # `<analysis>` 推理草稿 + `<summary>` 对话回放，一个字节都不是给用户看的。
        # 于是机检冤枉模型「没贴看板」，而回复里的「用户消息 N」也被读成"复述用户"。
        scratch = (
            "<analysis>Let me chronologically work through this conversation.\n"
            "**Message 1 (user):** 回放用户原话，这段绝不该被当成对外回复。</analysis>\n"
            "<summary>**当前请求（用户消息 4）**: 更多回放</summary>"
        )
        write_session(sessions / f"rollout-2026-09-26T10-00-00-{UID}.jsonl", scratch)
        after = subprocess.run(
            [
                sys.executable, str(BOOT), str(root),
                "--intent", f"{TICKET} 继续",
                "--thread-id", UID,
                "--sessions-root", str(root / "sessions"),
            ],
            text=True, capture_output=True,
        )
        # 草稿里没有看板，但也**没有真实回复**——这属于「不可判定」，不该判成「漏贴」。
        assert "上轮回复缺失任务看板" not in after.stdout, (
            "把模型草稿当成了对外回复并据此点名：" + after.stdout[-1500:]
        )
        assert "上轮回复无法判定" in after.stdout, (
            "观测量缺失时应照实说无法判定：" + after.stdout[-1500:]
        )

        # 反向：草稿 + 真回复同处一个 last_agent_message 时，必须看穿草稿读到真回复。
        write_session(
            sessions / f"rollout-2026-09-26T11-00-00-{UID}.jsonl",
            "<analysis>推理草稿：这里提到「任务状态看板」但不算贴出</analysis>\n"
            "### 📊 任务状态看板\n\n"
            "## 🎯 当前聚焦待办 (P0)\n- 无\n\n"
            "## ⏳ 待人工验收 (Pending Verification)\n- 无\n\n"
            "## 📦 已完结归档 (Archived in flow/history/)\n- 无\n\n"
            "## 💡 本轮决策记录 (Decisions)\n- 无\n",
        )
        mixed = subprocess.run(
            [
                sys.executable, str(BOOT), str(root),
                "--intent", f"{TICKET} 继续",
                "--thread-id", UID,
                "--sessions-root", str(root / "sessions"),
            ],
            text=True, capture_output=True,
        )
        assert "上轮回复缺失任务看板" not in mixed.stdout, (
            "草稿+真回复混合时误判为漏贴：" + mixed.stdout[-1500:]
        )

        # SPE-6（回退路径）：没有 `response_item` 正文时，`last_agent_message` 兜底也必须剥草稿。
        # 现场：老会话只有 event_msg，没有 role=="assistant" 的 response_item。
        legacy = sessions / f"rollout-2026-09-26T12-00-00-{UID}.jsonl"
        legacy.write_text(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "<analysis>草稿</analysis>"
                        "<summary>**当前请求（用户消息 4）**: 回放</summary>",
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        import importlib.util as _ilu

        spec = _ilu.spec_from_file_location("fb_under_test", BUDGET)
        fb = _ilu.module_from_spec(spec)
        spec.loader.exec_module(fb)
        assert fb.last_visible_reply([legacy]) == "", "回退路径没剥草稿"
        assert fb.board_visible(fb.last_visible_reply([legacy])) is False

        # SPE-1/2/3（2026-09-26 用户指派）：board_visible 必须锚定真看板的分区标题，
        # 不能靠「任务状态看板」「当前聚焦待办」两个词的 in 判断——实测 5 段非看板文本有 3 段假阳性。
        import importlib.util as _ilu2

        spec2 = _ilu2.spec_from_file_location("fb_board", BUDGET)
        fb2 = _ilu2.module_from_spec(spec2)
        spec2.loader.exec_module(fb2)

        # 真看板（四分区齐全）→ 必须判为已贴（严格化不得误报）
        real_board = (
            "### \U0001f4ca 任务状态看板\n\n"
            "## \U0001f3af 当前聚焦待办 (P0)\n- 无\n\n"
            "## \u23f3 待人工验收 (Pending Verification)\n- 无\n\n"
            "## \U0001f4e6 已完结归档 (Archived in flow/history/)\n- 无\n\n"
            "## \U0001f4a1 本轮决策记录 (Decisions)\n- 无\n"
        )
        assert fb2.board_visible(real_board), "真看板被判为未贴"

        # 空承诺 / 讨论 bug / 引用规则原文 → 一律不得判为已贴
        fakes = {
            "空承诺": "本轮我确保会输出「任务状态看板」和「当前聚焦待办」两段。",
            "讨论bug": "修复了任务状态看板里当前聚焦待办分区渲染错误的问题。",
            "引用规则": "判据：回复里必须同时出现「任务状态看板」与「当前聚焦待办」。",
            "只有大标题": "### \U0001f4ca 任务状态看板\n\n（本轮无内容）",
            # 四个任意二级标题：分区键若退化成 `## ` 就会被误判为已贴。
            "四个无关二级标题": "## 甲\n- 1\n\n## 乙\n- 2\n\n## 丙\n- 3\n\n## 丁\n- 4",
            # 三个无关标题 + 真决策标题：分区键若退化成 `## `，前三个会被误认。
            "三个无关+真决策标题": "## 甲\n\n## 乙\n\n## 丙\n\n## \U0001f4a1 本轮决策记录 (Decisions)\n- 无",
        }
        for label, text in fakes.items():
            assert not fb2.board_visible(text), f"{label} 被误判为已贴看板：{text}"

        # SPE-2：分区契约单一真相源——flow-budget 必须从 flow-deliver 派生，不另抄 emoji
        assert hasattr(fb2, "BOARD_SECTION_KEYS"), "缺少派生的分区键"
        deliver_src = (ROOT / "scripts" / "flow-deliver.py").read_text(encoding="utf-8")
        for heading in fb2.BOARD_SECTION_KEYS:
            assert heading in deliver_src, f"分区标题 {heading!r} 不在 flow-deliver 契约里"

    print("PASS: board lists real archives, decisions stay whole, missing board is called out")


if __name__ == "__main__":
    main()
