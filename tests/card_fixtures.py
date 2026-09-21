"""任务卡测试夹具：供多个回归测试复用，避免重复造卡。"""
from __future__ import annotations

from pathlib import Path


def write_block_scalar_card(path: Path) -> None:
    """写入一张使用 YAML 块标量的任务卡。"""
    path.write_text(
        "\n".join(
            [
                "ticket_id: T-BLOCK",
                "goal: 验证块标量解析",
                "mode: execute",
                "method: TDD",
                "write_whitelist: src/a.py",
                "verify_command: >",
                "  python3 tests/a.py",
                "  && echo done",
                "acceptance: >",
                "  Given A",
                "  When B",
                "  Then C",
            ]
        ),
        encoding="utf-8",
    )
