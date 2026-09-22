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

# v2 任务卡：把 Plan/SDD/TDD/ATDD/BDD 从“字段里有这个词”升级为“产物必须存在”。
# 老卡没有 schema 标记，继续走原规则，避免一次性推翻所有在途任务。
STRICT_SCHEMA = "v2"
SCOPE_REQUIRED_PARTS = ("输入", "输出", "边界")


def find_project_root(card: Path) -> Path | None:
    """从任务卡向上找到含 flow/ 的项目根。"""
    for parent in card.resolve().parents:
        if parent.name == "flow":
            return parent.parent
        if (parent / "flow").is_dir():
            return parent
    return None


def _is_real_path(card: Path, raw: str) -> bool:
    """字段里的路径是否真的存在于磁盘。

    只取首个看起来像路径的片段，允许 `path Exit 0` 这类带说明的写法。
    """
    root = find_project_root(card) or card.parent
    for token in re.split(r"[\s,，;；]+", raw.strip()):
        token = token.strip("`（）()[]")
        if not token or token in {">", "|", "-"}:
            continue
        if not re.search(r"[/\\.]", token) and not token.endswith((".py", ".ts", ".js", ".sh", ".md")):
            continue
        candidate = (root / token).resolve()
        if candidate.exists():
            return True
    return False


TEST_PATH_RE = re.compile(r"(^|/)(tests?|spec|__tests__)(/|$)|[._-](test|spec)\.", re.IGNORECASE)
TEST_MARKER_RE = re.compile(
    r"\b(assert|expect|should|describe|it\(|test\(|unittest|pytest|def test_|func Test)",
    re.IGNORECASE,
)


def _looks_like_test(card: Path, raw: str) -> bool:
    """red_test 指向的必须真的是测试：路径像测试，且正文有断言/用例特征。

    只校验“文件存在”会被 `red_test: README.md` 这类写法绕过——
    实测该写法可以通过旧规则，等于没证明先红后绿。
    """
    root = find_project_root(card) or card.parent
    for token in re.split(r"[\s,，;；]+", raw.strip()):
        token = token.strip("`（）()[]")
        if not token or not re.search(r"[/\\.]", token):
            continue
        candidate = (root / token).resolve()
        if not candidate.is_file():
            continue
        if not (TEST_PATH_RE.search(token) or candidate.name.startswith("test_")):
            continue
        try:
            body = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if TEST_MARKER_RE.search(body):
            return True
    return False


def validate_strict(card: Path, values: dict[str, str], phase: str) -> list[str]:
    """v2 卡的阶段产物校验：每个驱动模式必须有可验证产物。"""
    errors: list[str] = []
    scope = values.get("scope", "").strip()
    acceptance = values.get("acceptance", "").strip()

    # SDD：plan 阶段必须把输入、输出、边界写全，否则拆解没有依据。
    if phase == "plan":
        missing = [part for part in SCOPE_REQUIRED_PARTS if part not in scope]
        if missing:
            errors.append(
                f"SDD 规格不完整：scope 缺少 {'、'.join(missing)}；"
                f"必须写明输入、输出、边界，否则无法据此拆解原子任务"
            )

    # TDD：execute 阶段必须留下一个真实存在的失败测试证据。
    if phase == "execute":
        red = values.get("red_test", "").strip()
        if not red:
            errors.append("TDD 缺 red_test：必须填写先失败测试的文件路径（先红后绿）")
        elif not _is_real_path(card, red):
            errors.append(f"TDD red_test 指向的文件不存在：{red}")
        elif not _looks_like_test(card, red):
            errors.append(
                f"TDD red_test 不是测试文件或不含断言：{red}；"
                f"必须指向 tests/ 或 test_*/ 且含 assert/expect/test( 等用例特征"
            )

    # ATDD：review 阶段证据必须落到真实文件，而不是一句“已验证”。
    if phase == "review":
        evidence = values.get("evidence", "").strip()
        if evidence and not _is_real_path(card, evidence):
            errors.append(f"ATDD 证据文件不存在：{evidence}")

    # BDD：收尾交接必须给出结构化行为描述。
    if phase in {"review", "handoff"}:
        if "Given" not in acceptance or "Then" not in acceptance:
            errors.append("BDD 验收必须写成 Given-When-Then，用可观测行为描述结果")

    return errors


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
    if values.get("schema", "").strip().lower() == STRICT_SCHEMA:
        errors.extend(validate_strict(path, values, phase))
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
