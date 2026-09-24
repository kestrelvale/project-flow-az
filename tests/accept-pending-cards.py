#!/usr/bin/env python3
"""ATDD 验收：把 4 张 [-] 待验收卡片的 Given-When-Then 落成可执行断言。

用途：人工验收时不再靠「看着像通过了」销账。每条断言都跑真实命令并断言可观测结果，
全部通过才算可归档；任一条失败则非零退出，对应卡片继续留在 [-]。

对应卡片：
  PFP-ORPHAN-RECEIPT-20260923       孤儿熔断回执可显式作废
  PFP-STOP-RECEIPT-SELFREF-20260924 回执自引用不再永久阻塞新会话
  PFP-RELAY-CLARITY-20260924        撤字节上限 + 接力提示词自包含
  PFP-RELEASE-20260923              v4.15.0→4.15.13 十四个版本已推远端
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def run(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TESTS / script)], text=True, capture_output=True, cwd=ROOT
    )


def main() -> None:
    checks: list[tuple[str, bool, str]] = []

    # 1) 三张已交付卡各自的验收脚本（TDD 回归 + ATDD 行为断言）。
    for ticket, script in (
        ("PFP-ORPHAN-RECEIPT-20260923", "test-orphan-receipt.py"),
        ("PFP-STOP-RECEIPT-SELFREF-20260924", "test-stop-receipt-selfref.py"),
        ("PFP-RELAY-CLARITY-20260924", "test-relay-clarity.py"),
    ):
        result = run(script)
        checks.append((f"{ticket} · {script}", result.returncode == 0, result.stdout.strip()[-160:]))

    # 2) 撤字节上限要真的落到实现里（防止文档改了、代码没改）。
    boot_src = (ROOT / "scripts" / "flow-boot.py").read_text(encoding="utf-8")
    checks.append(("交接棒字节上限已撤（flow-boot.py 无 MAX_HANDOFF_BYTES）",
                   "MAX_HANDOFF_BYTES" not in boot_src, ""))

    # 3) 接力提示词生成器必须带工作根与真实任务卡路径。
    budget_src = (ROOT / "scripts" / "flow-budget.py").read_text(encoding="utf-8")
    checks.append(("提示词模板含工作根与 tasks/specs 实路径",
                   "工作根：" in budget_src and "flow/tasks/{ticket}.md" in budget_src, ""))

    # 4) PFP-RELEASE：远端 HEAD == 本地 HEAD（十四个版本确实推上去了），
    #    且交付说明可达、版本号与 CHANGELOG 顶部一致、全量回归 Exit 0。
    # 不用 `git rev-parse`：非 login 的 Python 子进程里 /usr/bin/git 会因 xcrun shim 失败
    # （实测 `unable to load libxcrun`），直接读 refs 文件是同等的可观测证据。
    head = (ROOT / ".git" / "refs" / "heads" / "main").read_text(encoding="utf-8").strip()
    remote = (ROOT / ".git" / "refs" / "remotes" / "origin" / "main").read_text(encoding="utf-8").strip()
    checks.append((f"origin/main 与本地 main 同步（{head[:7]}）", bool(head) and head == remote, f"remote={remote[:7]}"))

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    changelog_top = re.search(r"(?m)^## \[(\d+\.\d+\.\d+)\]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    checks.append((f"VERSION == CHANGELOG 顶部（{version}）",
                   bool(changelog_top) and changelog_top.group(1) == version, ""))

    handover = ROOT / "references" / "交付说明-v4.15.0-4.15.12.md"
    checks.append(("交付说明可达 references/交付说明-v4.15.0-4.15.12.md", handover.is_file(), ""))

    regression = subprocess.run(["bash", str(TESTS / "run-all.sh")], text=True, capture_output=True, cwd=ROOT)
    passed = regression.stdout.count("PASS")
    checks.append((f"全量回归 Exit 0（{passed} 项 PASS）",
                   regression.returncode == 0 and passed >= 19, regression.stdout.strip().splitlines()[-1] if regression.stdout else ""))

    # 5) 每张待验收卡都得有交付回执（flow-boot 的机检口径）。
    receipts = {p.name.split("-", 2)[-1].replace(".json", "") for p in (ROOT / "flow" / "deliveries").glob("*.json")}
    for ticket in (
        "PFP-ORPHAN-RECEIPT-20260923",
        "PFP-STOP-RECEIPT-SELFREF-20260924",
        "PFP-RELAY-CLARITY-20260924",
        "PFP-RELEASE-20260923",
    ):
        checks.append((f"{ticket} 有交付回执", ticket in receipts, ""))

    width = max(len(name) for name, _, _ in checks)
    failed = 0
    for name, ok, note in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {note}")
        failed += 0 if ok else 1
    if failed:
        print(f"\n验收未通过：{failed} 条失败，对应卡片不得归档。")
        raise SystemExit(1)
    print(f"\n验收通过：{len(checks)} 条断言全绿，4 张卡可归档到 flow/history/tasks/。")


if __name__ == "__main__":
    main()
