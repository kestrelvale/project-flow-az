#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/assets/templates/.hooks/stop-doccheck.sh"

command -v jq >/dev/null 2>&1 || {
  echo "FAIL: jq is required" >&2
  exit 1
}

[ -x "$HOOK" ] || {
  echo "FAIL: hook is not executable: $HOOK" >&2
  exit 1
}

cd "$ROOT"
slug="$(basename "$PWD" | tr -c '[:alnum:]_.-' '_')"
nonce="$$-$(date +%s)"
claude_turn="project-flow-hook-test-${nonce}"
claude_key="$(printf '%s' "$claude_turn" | tr -c '[:alnum:]_.-' '_')"
marker="/tmp/claude-${slug}-stopcheck-${claude_key}"
trap 'rm -f "$marker"' EXIT
rm -f "$marker"

run_hook() {
  local tool="$1"
  local active="$2"
  local turn="$3"
  printf '%s' "{\"session_id\":\"project-flow-test\",\"turn_id\":\"$turn\",\"stop_hook_active\":$active}" |
    bash "$HOOK" "$tool"
}

codex_first="$(run_hook codex false "codex-first-${nonce}")"
printf '%s' "$codex_first" | jq -e '.continue == true and (keys | length == 1)' >/dev/null

codex_active="$(run_hook codex true "codex-active-${nonce}")"
printf '%s' "$codex_active" | jq -e '.continue == true and (keys | length == 1)' >/dev/null

claude_first="$(run_hook claude false "$claude_turn")"
printf '%s' "$claude_first" |
  jq -e '.decision == "block" and (.reason | contains("收工自检"))' >/dev/null

claude_active="$(run_hook claude true "$claude_turn")"
printf '%s' "$claude_active" | jq -e '.continue == true and (keys | length == 1)' >/dev/null

echo "PASS: Codex safe-pass and Claude single-continuation behavior"
