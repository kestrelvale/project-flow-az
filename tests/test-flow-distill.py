#!/usr/bin/env python3
"""规格点台账必须能挡住「假销账」，交接棒必须能挡住「原样照抄用户消息」。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "flow-distill.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow = root / "flow"
        specs = flow / "specs"
        specs.mkdir(parents=True)
        ledger = specs / "T1.md"
        ledger.write_text(
            "\n".join(
                [
                    "### ♻️ 规格点回收台账",
                    "- [x] SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
                    "- [ ] SPE-2 | 微简历附件真实上传 | 证据：",
                    "- [!] SPE-3 | 身份切换 | 证据：后端缺 broker_shop / 解除条件：后端补接口",
                ]
            ),
            encoding="utf-8",
        )
        ok = run("spec", "--project", str(root), "--ticket", "T1")
        assert ok.returncode == 0, ok.stderr or ok.stdout
        assert "未回收 2 条" in ok.stdout, ok.stdout
        assert "SPE-1" in ok.stdout and "SPE-3" in ok.stdout, ok.stdout
        assert "不得重复执行" in ok.stdout, ok.stdout

        # 假销账：标了完成却没证据，必须被拒——否则中断后没人知道哪条真做完。
        ledger.write_text(
            "\n".join(
                [
                    "- [x] SPE-1 | 登录四态 | 证据：pytest exit 0",
                    "- [x] SPE-2 | 附件上传 | 证据：",
                ]
            ),
            encoding="utf-8",
        )
        fake = run("spec", "--project", str(root), "--ticket", "T1")
        assert fake.returncode == 1, fake.stdout
        assert "不得假销账" in fake.stdout, fake.stdout

        ledger.write_text("- [ ] 缺编号条目 | 证据：\n", encoding="utf-8")
        broken = run("spec", "--project", str(root), "--ticket", "T1")
        assert broken.returncode == 1, broken.stdout
        assert "不符合台账格式" in broken.stdout, broken.stdout

        # 交接棒原样照抄用户消息（P0/P4 的真实形态）必须被拒。
        sessions = root / "sessions"
        sessions.mkdir()
        user_text = (
            "你是正杰全球聘 P4 求职者 H5 端 Agent。本轮要完成 25 行矩阵收口，"
            "补齐四态与真实接口，收工运行交付脚本并原样粘贴看板与验收卡。"
        ) * 6
        rollout = sessions / "rollout-2026-09-21T10-31-14-thread-t1.jsonl"
        rollout.write_text(
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_text}],
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (flow / "进展.md").write_text("## 交接棒\n" + user_text + "\n", encoding="utf-8")
        replay = run(
            "handoff",
            "--project",
            str(root),
            "--thread-id",
            "thread-t1",
            "--sessions-root",
            str(sessions),
        )
        assert replay.returncode == 1, replay.stdout
        assert "原样照抄用户消息" in replay.stdout, replay.stdout

        (flow / "进展.md").write_text(
            "\n".join(
                [
                    "## 2026-09-23 · T1 · 交接棒（SDD 蒸馏）",
                    "- 规格点 SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
                    "- 还剩：SPE-2 微简历附件真实上传（后端缺删除端点）",
                    "- 卡在哪：附件删除接口不存在 / 解除条件：后端补 DELETE 端点",
                    "- 下一步：开新会话按 flow/specs/T1.md 未回收项继续",
                ]
            ),
            encoding="utf-8",
        )
        distilled = run(
            "handoff",
            "--project",
            str(root),
            "--thread-id",
            "thread-t1",
            "--sessions-root",
            str(sessions),
        )
        assert distilled.returncode == 0, distilled.stdout
        assert "通过" in distilled.stdout, distilled.stdout
    print("PASS: flow-distill blocks fake spec write-off and verbatim handoff replay")


if __name__ == "__main__":
    main()
