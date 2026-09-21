#!/usr/bin/env python3
"""验证 project-flow 任务卡是否满足四阶段门禁。

阶段与驱动模式一一对应，按项目生命周期单向流转：
    plan    -> Plan / Goal / SDD   （项目初期：定目标、拆规格）
    execute -> TDD                 （实现期：先失败测试、再最小实现）
    review  -> ATDD                （验收期：可执行验收断言）
    handoff -> BDD                 （收尾期：Given-When-Then 交接下一步）
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

# goal 与 objective 互为别名：新卡用 goal，旧卡沿用 objective，二者至少有一个即可。
GOAL_ALIASES = ("goal", "objective")

REQUIRED = {
    "plan": ("ticket_id", "mode", "method", "scope", "write_whitelist", "acceptance"),
    "execute": ("ticket_id", "mode", "method", "write_whitelist", "verify_command", "acceptance"),
    "review": ("ticket_id", "mode", "method", "evidence", "acceptance"),
    "handoff": ("ticket_id", "mode", "method", "next_agent", "next_action", "write_whitelist"),
}

PLACEHOLDER_RE = re.compile(r"^(?:<[^>]+>|待确认|TODO|TBD|暂缺|未填写)$", re.IGNORECASE)
PHASE_METHOD = {"plan": "SDD", "execute": "TDD", "review": "ATDD", "handoff": "BDD"}


def parse_card(path: Path) -> dict[str, str]:
    """解析任务卡字段。

    只取顶层 `key: value` 行，忽略缩进正文；`key: >` / `key: |` 这类
    YAML 块标量只把后续缩进正文拼回来，避免把标记符本身当成字段值，
    导致交付卡与门禁读到 `>` 而不是真实内容。
    """
    values: dict[str, str] = {}
    current: str | None = None
    block: list[str] = []

    def flush() -> None:
        if current is None:
            return
        # 用换行连接，保留多行路径清单；单行命令字段后续自行 strip。
        joined = "\n".join(part.strip() for part in block if part.strip())
        values[current] = joined or values.get(current, "")

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith((" ", "\t")):
            if current is not None:
                block.append(line)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        flush()
        current = key.strip()
        block = []
        value = value.strip()
        if value in (">", "|", ">-", "|-", ">+", "|+"):
            values[current] = value
        else:
            values[current] = value
            current = None
    flush()
    for key, value in values.items():
        if value.strip() in (">", "|", ">-", "|-", ">+", "|+"):
            values[key] = ""
    return values


def validate(path: Path, phase: str) -> list[str]:
    if not path.is_file():
        return [f"缺少任务卡: {path}"]
    values = parse_card(path)
    errors = []
    goal = next((values.get(field, "").strip() for field in GOAL_ALIASES if values.get(field, "").strip()), "")
    if not goal:
        errors.append("缺少字段: goal（或兼容别名 objective）")
    elif PLACEHOLDER_RE.fullmatch(goal):
        errors.append("字段仍为占位符: goal")
    for field in REQUIRED[phase]:
        value = values.get(field, "").strip()
        if not value:
            errors.append(f"缺少字段: {field}")
        elif PLACEHOLDER_RE.fullmatch(value):
            errors.append(f"字段仍为占位符: {field}")
    mode = values.get("mode", "")
    methods = {item.strip().upper() for item in values.get("method", "").replace("->", ",").split(",") if item.strip()}
    if phase == "plan" and mode != "plan":
        errors.append("plan 阶段 mode 必须为 plan")
    if phase == "execute" and mode != "execute":
        errors.append("execute 阶段 mode 必须为 execute")
    if phase == "handoff" and not values.get("next_agent", "").lower().startswith("codex"):
        errors.append("handoff 阶段 next_agent 必须明确交给 Codex")
    required_method = PHASE_METHOD[phase]
    if required_method not in methods:
        errors.append(f"{phase} 阶段 method 必须包含 {required_method}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("card", type=Path)
    parser.add_argument("--phase", choices=sorted(REQUIRED), default="plan")
    args = parser.parse_args()
    errors = validate(args.card, args.phase)
    if errors:
        print(f"project-flow 门禁失败 [{args.phase}]: {args.card}")
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"project-flow 门禁通过 [{args.phase}]: {args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
