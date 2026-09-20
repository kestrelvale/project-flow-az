#!/usr/bin/env python3
"""交付卡最小测试：必须包含改动、验证、证据和 BDD 验收。"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "flow-deliver.py"
spec = importlib.util.spec_from_file_location("flow_deliver", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        card = Path(tmp) / "task.md"
        card.write_text(
            "\n".join(
                [
                    "ticket_id: T-1",
                    "objective: 修正登录失效",
                    "mode: execute",
                    "method: SDD,TDD,ATDD,BDD",
                    "write_whitelist: src/auth.ts,tests/auth.test.ts",
                    "verify_command: npm test -- auth",
                    "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
                    "evidence: tests/auth.test.ts Exit 0",
                ]
            ),
            encoding="utf-8",
        )
        output = module.render(
            module.parse_card(card),
            changed="src/auth.ts,tests/auth.test.ts",
            evidence="npm test -- auth Exit 0",
        )
        assert "实际改动" in output, output
        assert "允许边界" in output, output
        assert "自动验证" in output, output
        assert "验证证据" in output, output
        assert "Given-When-Then" in output, output
        assert "[-] 待人工验收" in output, output
        missing_changed = module.render(module.parse_card(card), changed="", evidence="")
        assert "未提供；不得以 write_whitelist 冒充实际改动" in missing_changed, missing_changed
    print("PASS: flow-deliver emits a complete acceptance card")


if __name__ == "__main__":
    main()
