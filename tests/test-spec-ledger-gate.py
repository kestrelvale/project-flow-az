#!/usr/bin/env python3
"""规格点台账是进入 review/handoff 的硬门槛：未回收 / 假销账必须拦，显式豁免才放行。"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "flow-gate.py"
spec = importlib.util.spec_from_file_location("flow_gate", GATE)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

CARD = "\n".join(
    [
        "ticket_id: T-1",
        "schema: v2",
        "objective: 修正登录失效",
        "mode: review",
        "method: SDD,TDD,ATDD,BDD",
        "scope: 输入=登录请求；输出=有效令牌；边界=不做注册",
        "write_whitelist: src/auth.ts",
        "red_test: tests/test_auth.py",
        "verify_command: python3 tests/test_auth.py",
        "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
        "evidence: ev.txt",
        "next_agent: Codex Plan Mode",
        "next_action: 交接",
        "spec_ledger: flow/specs/T-1.md",
    ]
)


def errors(root: Path) -> list[str]:
    return gate.validate(root / "flow" / "tasks" / "T.md", "review")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "flow" / "tasks").mkdir(parents=True)
        (root / "flow" / "specs").mkdir()
        (root / "tests").mkdir()
        (root / "tests" / "test_auth.py").write_text("assert True\n", encoding="utf-8")
        (root / "ev.txt").write_text("Exit 0\n", encoding="utf-8")
        card = root / "flow" / "tasks" / "T.md"
        ledger = root / "flow" / "specs" / "T-1.md"

        # 1) 台账缺失 → 拦
        card.write_text(CARD, encoding="utf-8")
        missing = errors(root)
        assert any("缺少规格点台账" in e for e in missing), missing

        # 2) 有未回收项 → 拦（这正是「中断后重复执行同一需求点」的根因）
        ledger.write_text(
            "\n".join(
                [
                    "- [x] SPE-1 | 登录四态补齐 | 证据：pytest exit 0",
                    "- [ ] SPE-2 | 附件真实上传 | 证据：",
                ]
            ),
            encoding="utf-8",
        )
        pending = errors(root)
        assert any("未回收" in e and "SPE-2" in e for e in pending), pending

        # 3) 假销账（标完成却没证据）→ 拦
        ledger.write_text("- [x] SPE-1 | 登录四态 | 证据：\n", encoding="utf-8")
        fake = errors(root)
        assert any("假销账" in e for e in fake), fake

        # 4) 全部回收且有证据 → 放行
        ledger.write_text(
            "- [x] SPE-1 | 登录四态补齐 | 证据：pytest exit 0\n", encoding="utf-8"
        )
        assert errors(root) == [], errors(root)

        # 5) 显式豁免（琐碎卡）才放行，且必须留痕
        card.write_text(CARD.replace("flow/specs/T-1.md", "none"), encoding="utf-8")
        ledger.unlink()
        assert errors(root) == [], errors(root)
    print("PASS: spec ledger gate blocks pending/fake write-off, allows explicit exempt")


if __name__ == "__main__":
    main()
