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
nonce="$$-$(date +%s)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/project-flow-stop-hook-test.XXXXXX")"
fake_bin="$test_root/bin"
no_jq_bin="$test_root/no-jq-bin"
minimal_bin="$test_root/minimal-bin"
marker_root="/tmp/project-flow-stopcheck-${UID}"
markers=""
mkdir -p "$fake_bin" "$no_jq_bin" "$minimal_bin"

cat > "$fake_bin/codex" <<'EOF'
#!/bin/sh
printf 'codex-cli %s\n' "${PROJECT_FLOW_FAKE_CODEX_VERSION:-0.145.0}"
EOF
chmod +x "$fake_bin/codex"

for command_name in awk cat; do
  command_path="$(command -v "$command_name")"
  ln -s "$command_path" "$no_jq_bin/$command_name"
done
ln -s "$fake_bin/codex" "$no_jq_bin/codex"
for command_name in awk cat jq mkdir; do
  command_path="$(command -v "$command_name")"
  ln -s "$command_path" "$minimal_bin/$command_name"
done
ln -s "$fake_bin/codex" "$minimal_bin/codex"

marker_for() {
  local tool="$1"
  local session="$2"
  local scope="$3"
  printf '%s/%s-%s-%s-%s-%s' \
    "$marker_root" "$tool" "${#session}" "$session" "${#scope}" "$scope"
}

remember_marker() {
  local marker="$1"
  markers="${markers}
${marker}"
  rmdir "$marker" 2>/dev/null || true
}

cleanup() {
  printf '%s\n' "$markers" | while IFS= read -r marker; do
    [ -n "$marker" ] && rmdir "$marker" 2>/dev/null || true
  done
  rm -rf "$test_root"
}
trap cleanup EXIT

run_raw() {
  local tool="$1"
  local version="$2"
  local payload="$3"
  printf '%s' "$payload" |
    env PATH="$fake_bin:$PATH" PROJECT_FLOW_FAKE_CODEX_VERSION="$version" \
      bash "$HOOK" "$tool"
}

run_hook() {
  local tool="$1"
  local active="$2"
  local session="$3"
  local scope="$4"
  local version="${5:-0.145.0}"
  local scope_field
  if [ "$tool" = "codex" ]; then
    scope_field="turn_id"
  else
    scope_field="prompt_id"
  fi
  run_raw "$tool" "$version" \
    "{\"session_id\":\"$session\",\"$scope_field\":\"$scope\",\"stop_hook_active\":$active}"
}

assert_block() {
  local output="$1"
  local docname="$2"
  printf '%s' "$output" |
    jq -e --arg docname "$docname" '
      .decision == "block"
      and (.reason | contains("收工自检"))
      and (.reason | contains($docname))
    ' >/dev/null
}

assert_continue() {
  local output="$1"
  printf '%s' "$output" |
    jq -e '.continue == true' >/dev/null
}

for tool in codex claude; do
  if [ "$tool" = "codex" ]; then
    docname="AGENTS.md"
  else
    docname="CLAUDE.md"
  fi

  session="${tool}-session-${nonce}"
  first_scope="${tool}-first-${nonce}"
  first_marker="$(marker_for "$tool" "$session" "$first_scope")"
  remember_marker "$first_marker"

  assert_block "$(run_hook "$tool" false "$session" "$first_scope")" "$docname"
  [ -d "$first_marker" ] || {
    echo "FAIL: first Stop did not create atomic marker: $first_marker" >&2
    exit 1
  }
  assert_continue "$(run_hook "$tool" true "$session" "$first_scope")"
  [ -d "$first_marker" ] || {
    echo "FAIL: active continuation removed its marker: $first_marker" >&2
    exit 1
  }
  for _ in 1 2 3; do
    assert_continue "$(run_hook "$tool" false "$session" "$first_scope")"
  done

  second_scope="${tool}-second-${nonce}"
  second_marker="$(marker_for "$tool" "$session" "$second_scope")"
  remember_marker "$second_marker"
  assert_block "$(run_hook "$tool" false "$session" "$second_scope")" "$docname"

  active_scope="${tool}-active-first-${nonce}"
  active_marker="$(marker_for "$tool" "$session" "$active_scope")"
  remember_marker "$active_marker"
  assert_continue "$(run_hook "$tool" true "$session" "$active_scope")"
  [ -d "$active_marker" ] || {
    echo "FAIL: active-first Stop did not preserve a marker: $active_marker" >&2
    exit 1
  }
  assert_continue "$(run_hook "$tool" false "$session" "$active_scope")"
done

shared_scope="shared-scope-${nonce}"
for session in "session-a-${nonce}" "session-b-${nonce}"; do
  marker="$(marker_for codex "$session" "$shared_scope")"
  remember_marker "$marker"
  assert_block "$(run_hook codex false "$session" "$shared_scope")" "AGENTS.md"
done

collision_scope_suffix="collision-${nonce}"
for pair in "a-b:c-${collision_scope_suffix}" "a:b-c-${collision_scope_suffix}"; do
  session="${pair%%:*}"
  scope="${pair#*:}"
  marker="$(marker_for codex "$session" "$scope")"
  remember_marker "$marker"
  assert_block "$(run_hook codex false "$session" "$scope")" "AGENTS.md"
done

cross_session="cross-tool-session-${nonce}"
cross_scope="cross-tool-scope-${nonce}"
for tool in codex claude; do
  marker="$(marker_for "$tool" "$cross_session" "$cross_scope")"
  remember_marker "$marker"
  if [ "$tool" = "codex" ]; then
    assert_block "$(run_hook "$tool" false "$cross_session" "$cross_scope")" "AGENTS.md"
  else
    assert_block "$(run_hook "$tool" false "$cross_session" "$cross_scope")" "CLAUDE.md"
  fi
done

pwd_session="pwd-session-${nonce}"
pwd_scope="pwd-scope-${nonce}"
pwd_marker="$(marker_for codex "$pwd_session" "$pwd_scope")"
remember_marker "$pwd_marker"
mkdir -p "$test_root/pwd-a" "$test_root/pwd-b"
assert_block "$(
  cd "$test_root/pwd-a"
  run_hook codex false "$pwd_session" "$pwd_scope"
)" "AGENTS.md"
assert_continue "$(
  cd "$test_root/pwd-b"
  run_hook codex false "$pwd_session" "$pwd_scope"
)"

old_marker="$(marker_for codex "old-session-${nonce}" "old-turn-${nonce}")"
remember_marker "$old_marker"
assert_continue "$(run_hook codex false "old-session-${nonce}" "old-turn-${nonce}" "0.144.1")"
[ ! -e "$old_marker" ] || {
  echo "FAIL: incompatible Codex version created a marker" >&2
  exit 1
}
assert_continue "$(run_hook codex false "unknown-session-${nonce}" "unknown-turn-${nonce}" "unknown")"

assert_continue "$(run_raw codex "0.145.0" '{"session_id":"missing-scope"}')"
assert_continue "$(run_raw claude "0.145.0" '{"prompt_id":"missing-session"}')"
codex_wrong_marker="$(marker_for codex "codex-wrong-session-${nonce}" "codex-wrong-prompt-${nonce}")"
remember_marker "$codex_wrong_marker"
assert_continue "$(
  run_raw codex "0.145.0" \
    "{\"session_id\":\"codex-wrong-session-${nonce}\",\"prompt_id\":\"codex-wrong-prompt-${nonce}\"}"
)"
[ ! -e "$codex_wrong_marker" ] || {
  echo "FAIL: Codex accepted prompt_id instead of required turn_id" >&2
  exit 1
}
claude_wrong_marker="$(marker_for claude "claude-wrong-session-${nonce}" "claude-wrong-turn-${nonce}")"
remember_marker "$claude_wrong_marker"
assert_continue "$(
  run_raw claude "0.145.0" \
    "{\"session_id\":\"claude-wrong-session-${nonce}\",\"turn_id\":\"claude-wrong-turn-${nonce}\"}"
)"
[ ! -e "$claude_wrong_marker" ] || {
  echo "FAIL: Claude accepted turn_id instead of required prompt_id" >&2
  exit 1
}
for payload in '' 'not-json' '[]' '42' '{"session_id":42,"turn_id":"t"}' '{"session_id":"s","turn_id":{}}'; do
  assert_continue "$(run_raw codex "0.145.0" "$payload")"
done
assert_continue "$(
  run_raw codex "0.145.0" \
    "{\"session_id\":\"unsafe/session-${nonce}\",\"turn_id\":\"unsafe-turn-${nonce}\"}"
)"

no_jq_output="$(
  printf '%s' '{"session_id":"s","turn_id":"t","stop_hook_active":false}' |
    env PATH="$no_jq_bin" PROJECT_FLOW_FAKE_CODEX_VERSION="0.145.0" \
      /bin/bash "$HOOK" codex
)"
assert_continue "$no_jq_output"

minimal_session="minimal-session-${nonce}"
minimal_scope="minimal-turn-${nonce}"
minimal_marker="$(marker_for codex "$minimal_session" "$minimal_scope")"
remember_marker "$minimal_marker"
minimal_output="$(
  printf '%s' \
    "{\"session_id\":\"$minimal_session\",\"turn_id\":\"$minimal_scope\",\"stop_hook_active\":false}" |
    env PATH="$minimal_bin" PROJECT_FLOW_FAKE_CODEX_VERSION="0.145.0" \
      /bin/bash "$HOOK" codex
)"
assert_block "$minimal_output" "AGENTS.md"
[ -d "$minimal_marker" ] || {
  echo "FAIL: hook did not work without external tr/id commands" >&2
  exit 1
}

concurrent_session="concurrent-session-${nonce}"
concurrent_scope="concurrent-turn-${nonce}"
concurrent_marker="$(marker_for codex "$concurrent_session" "$concurrent_scope")"
remember_marker "$concurrent_marker"
for index in 1 2 3 4 5 6 7 8; do
  (
    run_hook codex false "$concurrent_session" "$concurrent_scope" \
      > "$test_root/concurrent-$index.json"
  ) &
done
wait
block_count="$(
  jq -s '[.[] | select(.decision == "block")] | length' \
    "$test_root"/concurrent-*.json
)"
continue_count="$(
  jq -s '[.[] | select(.continue == true)] | length' \
    "$test_root"/concurrent-*.json
)"
[ "$block_count" -eq 1 ] && [ "$continue_count" -eq 7 ] || {
  echo "FAIL: concurrent first Stop expected 1 block and 7 continue; got $block_count/$continue_count" >&2
  exit 1
}

echo "PASS: version-gated Codex and Claude Code single-continuation behavior"
