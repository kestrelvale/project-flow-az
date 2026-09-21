#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v jq >/dev/null 2>&1 || {
  echo "FAIL: jq is required" >&2
  exit 1
}

require_file() {
  local path="$1"
  [ -f "$ROOT/$path" ] || {
    echo "FAIL: missing $path" >&2
    exit 1
  }
}

require_text() {
  local path="$1"
  local text="$2"
  grep -Fq -- "$text" "$ROOT/$path" || {
    echo "FAIL: $path does not contain: $text" >&2
    exit 1
  }
}

require_file "references/多子项目结构.md"
require_file "assets/templates/MODULE_AGENTS.md"
require_file "assets/templates/AGENTS.md"
require_file "evals/evals.json"
require_file "scripts/audit-flow.py"
require_file "scripts/flow-boot.py"

require_text "SKILL.md" "一个项目边界一个控制面"
require_text "SKILL.md" "assets/templates/MODULE_AGENTS.md"
require_text "references/初始化SOP.md" "不在子项目重复创建"
require_text "references/hook机制.md" "不安装 Hook，也不依赖 Hook"
require_text "references/hook机制.md" "flow/plan.md"
require_text "references/文档维护SOP.md" "规则就近,文档集中"
require_text "README.md" "单仓多子项目"
require_text "assets/templates/AGENTS.md" "project-flow 运行时合同"
require_text "assets/templates/AGENTS.md" "开工状态与收工看板"
require_text "assets/templates/AGENTS.md" "交付验收卡"
require_text "assets/templates/AGENTS.md" "flow-deliver.py"
require_text "assets/templates/AGENTS.md" "禁止只写“flow 状态”摘要"
require_text "assets/templates/AGENTS.md" "本轮工作汇报"
require_text "assets/templates/AGENTS.md" "--what"
require_text "assets/templates/AGENTS.md" "--why"
require_text "assets/templates/AGENTS.md" "--next-step"
require_text "assets/templates/AGENTS.md" "plan 先落盘"
require_text "assets/templates/AGENTS.md" "交付验收卡"
require_text "assets/templates/AGENTS.md" "收工写进展"
require_text "assets/templates/AGENTS.md" "flow-boot.py"
require_text "assets/templates/AGENTS.md" "--intent"
require_text "assets/templates/AGENTS.md" "接管路由"
require_text "assets/templates/AGENTS.md" "flow-budget.py"
require_text "assets/templates/AGENTS.md" "预算 [STOP]"
require_text "references/运行时入口与债务审计.md" "无 Hook"
require_text "references/运行时入口与债务审计.md" "flow-boot.py"
require_text "references/运行时入口与债务审计.md" "--intent"
require_text "references/hook机制.md" "--intent"
require_file "references/会话预算与接力SOP.md"
require_file "scripts/flow-budget.py"
require_file "scripts/flow-deliver.py"
require_file "tests/test-archive-layout.py"
require_file "assets/templates/flow/history/plans/.gitkeep"
require_file "assets/templates/flow/history/tasks/.gitkeep"
require_file "assets/templates/flow/history/progress/.gitkeep"
require_file "assets/templates/flow/trash/deprecated/.gitkeep"
require_file "assets/templates/flow/trash/verification/.gitkeep"
require_file "assets/templates/flow/gc/receipts/.gitkeep"
require_text "assets/templates/MODULE_AGENTS.md" "模块级接管与交接"
require_text "assets/templates/MODULE_AGENTS.md" "flow-budget.py"
require_text "references/多子项目结构.md" "模块级接管与交接"

if grep -R -n -E 'stop-doccheck|decision:block|turn_id|prompt_id' \
  "$ROOT/assets/templates" "$ROOT/references"; then
  echo "FAIL: stale Hook protocol remains" >&2
  exit 1
fi

if grep -R -n -E '5 份详规|5份详规|五份详规' \
  "$ROOT/SKILL.md" "$ROOT/README.md" "$ROOT/references"; then
  echo "FAIL: stale five-reference wording remains" >&2
  exit 1
fi

jq -e '
  (.skill_name == "project-flow-az" or .skill_name == "project-flow-cy") and
  (.evals | length) >= 4 and
  all(.evals[];
    (.prompt | type == "string" and length > 0) and
    (.expected_output | type == "string" and length > 0) and
    (.expectations | type == "array" and length > 0)
  )
' "$ROOT/evals/evals.json" >/dev/null

python3 -m py_compile \
  "$ROOT/scripts/audit-flow.py" \
  "$ROOT/scripts/sync-project.py" \
  "$ROOT/scripts/flow-boot.py" \
  "$ROOT/scripts/flow-deliver.py"

python3 "$ROOT/tests/test-audit-flow.py"
python3 "$ROOT/tests/test-flow-boot-routing.py"
python3 "$ROOT/tests/test-flow-budget.py"
python3 "$ROOT/tests/test-flow-gate.py"
python3 "$ROOT/tests/test-flow-deliver.py"
python3 "$ROOT/tests/test-archive-layout.py"

echo "PASS: multi-project structure rules and evals are consistent"
