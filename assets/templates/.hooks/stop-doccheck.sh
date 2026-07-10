#!/usr/bin/env bash
# Stop hook —— Claude 每回合收尾续跑一次自检;Codex 暂时只放行。
# 用法: stop-doccheck.sh [claude|codex]
tool="${1:-claude}"
slug="$(basename "$PWD" | tr -c '[:alnum:]_.-' '_')"
input="$(cat)"

# Codex CLI 0.144.1 已实证会把 decision:block 产生的 continuation prompt
# 保存为裸 UUID message id；下一次 Responses API 请求因此触发
# invalid_id_prefix。AGENTS.md 已包含同一套收工约束，所以在完成
# “停止→续发→重启恢复”回归前，Codex 默认安全放行、不自动续跑。
if [ "$tool" = "codex" ]; then
  printf '%s\n' '{"continue":true}'
  exit 0
fi

sid="$(printf '%s' "$input" | jq -r '.session_id // "nosid"' 2>/dev/null || echo nosid)"
turn="$(printf '%s' "$input" | jq -r '.turn_id // empty' 2>/dev/null || true)"
active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)"
key="${turn:-$sid}"
key="$(printf '%s' "$key" | tr -c '[:alnum:]_.-' '_')"
marker="/tmp/${tool}-${slug}-stopcheck-${key}"
docname="CLAUDE.md"; [ "$tool" = "codex" ] && docname="AGENTS.md"

if [ "$active" = "true" ] || [ -f "$marker" ]; then
  printf '%s\n' '{"continue":true}'        # 已续跑/触发过,放行避免循环
  exit 0
fi
touch "$marker" 2>/dev/null || true

reason="【收工自检】① 文档:本轮若有 结构/方案、心智模型、方向、外部资料、设计 变更 → 提议更新 ${docname}(注明层级)或 DESIGN.md,列出修改点等确认。② 交接:在 flow/进展.md 最上面追加一条进展(做了什么/为什么/怎么理解/产出路径/问题→解决/下一步)并把这条贴在回复里给用户看,决策落 decisions.md、坑落 踩坑记录.md。都没有就回复「无需更新」。"
jq -n --arg r "$reason" '{decision:"block", reason:$r}'
