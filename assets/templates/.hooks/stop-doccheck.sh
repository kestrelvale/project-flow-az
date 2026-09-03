#!/usr/bin/env bash
# Stop hook —— Claude Code / Codex 每个用户回合收尾续跑一次自检。
# 用法: stop-doccheck.sh [claude|codex]
tool="${1:-claude}"
input="$(cat)"

continue_safe() {
  printf '%s\n' '{"continue":true}'
  exit 0
}

codex_supports_continuation() {
  local version rest major minor patch
  version="$(codex --version 2>/dev/null | awk '{print $NF}')" || return 1
  case "$version" in
    *.*.*) ;;
    *) return 1 ;;
  esac
  major="${version%%.*}"
  rest="${version#*.}"
  minor="${rest%%.*}"
  patch="${rest#*.}"
  case "${major}:${minor}:${patch}" in
    *[!0-9:]* | :* | *: | *::* ) return 1 ;;
  esac
  [ "$major" -gt 0 ] || { [ "$major" -eq 0 ] && [ "$minor" -ge 145 ]; }
}

case "$tool" in
  claude)
    docname="CLAUDE.md"
    scope_field="prompt_id"
    ;;
  codex)
    docname="AGENTS.md"
    scope_field="turn_id"
    codex_supports_continuation || continue_safe
    ;;
  *)
    continue_safe
    ;;
esac

command -v jq >/dev/null 2>&1 || continue_safe
sid="$(printf '%s' "$input" | jq -r '
  if type == "object" and (.session_id | type) == "string"
  then .session_id else empty end
' 2>/dev/null || true)"
scope="$(printf '%s' "$input" | jq -r --arg field "$scope_field" '
  if type == "object"
    and (.[$field] | type) == "string"
    and (.[$field] | length > 0)
  then .[$field] else empty end
' 2>/dev/null || true)"
active="$(printf '%s' "$input" | jq -r '
  if type == "object" and .stop_hook_active == true then "true" else "false" end
' 2>/dev/null || echo false)"
[ -n "$sid" ] && [ -n "$scope" ] || continue_safe

case "${sid}:${scope}" in
  *[!A-Za-z0-9._:-]*) continue_safe ;;
esac
case "${UID:-}" in
  '' | *[!0-9]*) continue_safe ;;
esac
key="${#sid}-${sid}-${#scope}-${scope}"
marker_root="/tmp/project-flow-stopcheck-${UID}"
mkdir -p "$marker_root" 2>/dev/null || continue_safe
marker="$marker_root/${tool}-${key}"

if [ "$active" = "true" ]; then
  mkdir "$marker" 2>/dev/null || true
  continue_safe
fi

if ! mkdir "$marker" 2>/dev/null; then
  [ -d "$marker" ] && continue_safe
  continue_safe
fi

# Session Turn Counter & Context Health Guard
turn_counter_file="$marker_root/turn-count-${sid}"
current_turns=1
if [ -f "$turn_counter_file" ]; then
  prev_turns="$(cat "$turn_counter_file" 2>/dev/null || echo 0)"
  current_turns=$((prev_turns + 1))
fi
printf "%s" "$current_turns" > "$turn_counter_file" 2>/dev/null || true

relay_warning=""
if [ "$current_turns" -ge 8 ]; then
  relay_warning="\n\n⚠️【会话熔断与接力预警】当前会话已连续交互 ${current_turns} 个回合（历史上下文堆叠已达临界区）。为防模型发生语法退化或截断，请在汇报末尾明确提醒用户：所有成果已落盘实体，强烈建议在侧边栏新建 Task 开新会话，读取 flow/进展.md 接力！"
fi

reason="【收工自检】先读取当前路径生效的 ${docname}；若其中有业务专项收工检查，先执行该检查且不扩大本轮授权。① 文档:本轮若有 结构/方案、心智模型、方向、外部资料、设计 变更 → 提议更新对应层级的 ${docname} 或 DESIGN.md,列出修改点等确认。② 交接:在本 Hook 所属项目根的 flow/进展.md 最上面追加一条进展(做了什么/为什么/怎么理解/产出路径/问题→解决/下一步)并把这条贴在回复里给用户看,决策落 decisions.md、坑落 踩坑记录.md。都没有就回复「无需更新」。${relay_warning}"
jq -n --arg r "$reason" '{decision:"block", reason:$r}'
