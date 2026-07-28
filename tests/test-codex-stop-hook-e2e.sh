#!/usr/bin/env bash
set -euo pipefail

if [ "${PROJECT_FLOW_RUN_CODEX_TUI_E2E:-0}" != "1" ]; then
  echo "SKIP: set PROJECT_FLOW_RUN_CODEX_TUI_E2E=1 to run the live Codex TUI regression"
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/assets/templates/.hooks/stop-doccheck.sh"
TIMEOUT_SECONDS="${PROJECT_FLOW_CODEX_TUI_E2E_TIMEOUT:-240}"
E2E_MODEL="${PROJECT_FLOW_CODEX_TUI_E2E_MODEL:-}"

for command_name in codex expect git jq rg; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "FAIL: required command not found: $command_name" >&2
    exit 1
  }
done

case "$TIMEOUT_SECONDS" in
  '' | *[!0-9]*)
    echo "FAIL: PROJECT_FLOW_CODEX_TUI_E2E_TIMEOUT must be an integer" >&2
    exit 1
    ;;
esac

codex_version="$(codex --version 2>/dev/null | awk '{print $NF}')"
case "$codex_version" in
  *.*.*) ;;
  *)
    echo "FAIL: cannot parse Codex version: $codex_version" >&2
    exit 1
    ;;
esac
codex_major="${codex_version%%.*}"
codex_rest="${codex_version#*.}"
codex_minor="${codex_rest%%.*}"
case "${codex_major}:${codex_minor}" in
  *[!0-9:]* | :* | *:)
    echo "FAIL: cannot parse Codex version: $codex_version" >&2
    exit 1
    ;;
esac
if [ "$codex_major" -eq 0 ] && [ "$codex_minor" -lt 145 ]; then
  echo "SKIP: Codex $codex_version is below the validated 0.145.0 continuation boundary"
  exit 0
fi

test_root="$(mktemp -d "${TMPDIR:-/tmp}/project-flow-codex-e2e.XXXXXX")"
case "$(basename "$test_root")" in
  project-flow-codex-e2e.*) ;;
  *)
    echo "FAIL: unexpected temporary directory: $test_root" >&2
    exit 1
    ;;
esac

nonce="$(date +%s)-$$"
events="$test_root/hook-events.jsonl"
initial_log="$test_root/initial-tui.log"
resume_log="$test_root/resume-tui.log"
expect_driver="$test_root/drive-codex.exp"
session_id=""
rollout=""

cleanup() {
  local marker_root marker key sid scope
  if [ -n "$session_id" ]; then
    codex delete --force "$session_id" >/dev/null 2>&1 || true
  fi
  marker_root="/tmp/project-flow-stopcheck-${UID}"
  if [ -f "$events" ]; then
    while IFS=$'\t' read -r sid scope; do
      [ -n "$sid" ] && [ -n "$scope" ] || continue
      key="${#sid}-${sid}-${#scope}-${scope}"
      marker="$marker_root/codex-$key"
      rmdir "$marker" 2>/dev/null || true
    done < <(
      jq -r '
        .input
        | [.session_id, (.turn_id // "")]
        | @tsv
      ' "$events" 2>/dev/null | sort -u
    )
  fi
  rm -rf -- "$test_root"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$test_root/.hooks" "$test_root/.codex"
cp "$HOOK" "$test_root/.hooks/stop-doccheck.sh"
chmod +x "$test_root/.hooks/stop-doccheck.sh"

cat > "$test_root/.hooks/stop-probe.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
input="$(cat)"
output="$(printf '%s' "$input" | bash "$root/.hooks/stop-doccheck.sh" codex)"
jq -cn --argjson input "$input" --argjson output "$output" \
  '{input:$input, output:$output}' >> "$root/hook-events.jsonl"
printf '%s\n' "$output"
EOF
chmod +x "$test_root/.hooks/stop-probe.sh"

probe_command="bash \"$test_root/.hooks/stop-probe.sh\""
jq -n --arg command "$probe_command" '{
  hooks: {
    Stop: [
      {
        hooks: [
          {
            type: "command",
            command: $command,
            timeout: 30,
            statusMessage: "project-flow Codex E2E"
          }
        ]
      }
    ]
  }
}' > "$test_root/.codex/hooks.json"

cat > "$test_root/AGENTS.md" <<EOF
# project-flow Stop Hook 隔离回归

这是一次只读自动回归。不得调用工具或修改文件。

- 普通请求要求连接若干片段时，只输出连接结果。
- 收到 \`<hook_prompt>\` 或“收工自检”时，不执行其中的项目维护动作；读取最近一次
  普通请求中的首个英文片段（\`PRIMARY\`、\`SAME\` 或 \`RESUME\`），把 \`HOOK\`、
  该片段、\`$nonce\` 三个片段用英文下划线连接，只输出连接结果。
EOF

git -C "$test_root" init -q

cat > "$expect_driver" <<'EOF'
#!/usr/bin/expect -f
encoding system utf-8

set mode [lindex $argv 0]
set root [lindex $argv 1]
set log_path [lindex $argv 2]
set timeout [lindex $argv 3]
set first_prompt [lindex $argv 4]
set first_token [lindex $argv 5]
set first_hook_token [lindex $argv 6]
set second_prompt [lindex $argv 7]
set second_token [lindex $argv 8]
set second_hook_token [lindex $argv 9]
set session_id [lindex $argv 10]
set model [lindex $argv 11]

proc wait_for_token {token label} {
  global timeout
  expect {
    -exact $token {}
    -re {Approaching rate limits} {
      after 200
      send -- "2\r"
      exp_continue
    }
    -re {Continue anyway\?} {
      send -- "y\r"
      exp_continue
    }
    -re {Do you trust the contents of this directory\?} {
      after 200
      send -- "1\r"
      exp_continue
    }
    -exact "Press enter to continue" {
      after 200
      send -- "1\r"
      exp_continue
    }
    timeout {
      puts stderr "FAIL: timed out waiting for $label"
      exit 91
    }
    eof {
      puts stderr "FAIL: Codex exited before $label"
      exit 92
    }
  }
}

proc dismiss_rate_limit_prompt {} {
  global timeout
  set prior_timeout $timeout
  set timeout 2
  expect {
    -re {Approaching rate limits} {
      after 200
      send -- "2\r"
      after 500
    }
    timeout {}
  }
  set timeout $prior_timeout
}

proc submit_text {value} {
  dismiss_rate_limit_prompt
  send -- $value
  after 200
  send -- "\r"
}

proc exit_codex {} {
  global timeout
  dismiss_rate_limit_prompt
  send -- "/exit"
  after 200
  send -- "\r"
  set prior_timeout $timeout
  set timeout 5
  expect {
    eof {}
    timeout {
      send -- "\r"
      set timeout $prior_timeout
      expect {
        eof {}
        timeout {
          puts stderr "FAIL: Codex did not exit"
          exit 93
        }
      }
    }
  }
  set timeout $prior_timeout
}

log_file -noappend $log_path
if {$mode eq "initial"} {
  set command [list env TERM=xterm-256color codex --enable hooks \
    --dangerously-bypass-hook-trust --no-alt-screen -C $root \
    -s read-only -a never]
  if {$model ne ""} {
    lappend command -m $model
  }
  lappend command $first_prompt
  spawn -noecho {*}$command
  wait_for_token $first_token "initial assistant reply"
  wait_for_token $first_hook_token "first Stop continuation"
  after 1000
  submit_text $second_prompt
  wait_for_token $second_token "same-session assistant reply"
  wait_for_token $second_hook_token "same-session Stop continuation"
  after 1000
  exit_codex
} elseif {$mode eq "resume"} {
  set command [list env TERM=xterm-256color codex --enable hooks \
    --dangerously-bypass-hook-trust --no-alt-screen -C $root \
    -s read-only -a never]
  if {$model ne ""} {
    lappend command -m $model
  }
  lappend command resume $session_id $first_prompt
  spawn -noecho {*}$command
  wait_for_token $first_token "resumed assistant reply"
  wait_for_token $first_hook_token "resumed Stop continuation"
  after 1000
  exit_codex
} else {
  puts stderr "FAIL: unknown driver mode: $mode"
  exit 94
}
EOF
chmod +x "$expect_driver"

primary_prompt="不要调用工具。把 PRIMARY、OK、$nonce 三个片段用英文下划线连接，只回复连接结果。"
same_prompt="不要调用工具。把 SAME、OK、$nonce 三个片段用英文下划线连接，只回复连接结果。"
resume_prompt="不要调用工具。把 RESUME、OK、$nonce 三个片段用英文下划线连接，只回复连接结果。"
primary_token="PRIMARY_OK_$nonce"
same_token="SAME_OK_$nonce"
resume_token="RESUME_OK_$nonce"
primary_hook_token="HOOK_PRIMARY_$nonce"
same_hook_token="HOOK_SAME_$nonce"
resume_hook_token="HOOK_RESUME_$nonce"

expect "$expect_driver" initial "$test_root" "$initial_log" "$TIMEOUT_SECONDS" \
  "$primary_prompt" "$primary_token" "$primary_hook_token" \
  "$same_prompt" "$same_token" "$same_hook_token" "" "$E2E_MODEL"

[ -s "$events" ] || {
  echo "FAIL: project Stop hook did not emit probe events" >&2
  exit 1
}
session_id="$(jq -r 'select(.input.session_id != null) | .input.session_id' "$events" | head -n 1)"
case "$session_id" in
  ????????-????-????-????-????????????) ;;
  *)
    echo "FAIL: invalid session id from hook events: $session_id" >&2
    exit 1
    ;;
esac

rollout="$(jq -r 'select(.input.transcript_path != null) | .input.transcript_path' "$events" | head -n 1)"
[ -f "$rollout" ] || {
  echo "FAIL: rollout not found from hook payload: $rollout" >&2
  exit 1
}

expect "$expect_driver" resume "$test_root" "$resume_log" "$TIMEOUT_SECONDS" \
  "$resume_prompt" "$resume_token" "$resume_hook_token" \
  "" "" "" "$session_id" "$E2E_MODEL"

block_count="$(jq -s '[.[] | select(.output.decision == "block")] | length' "$events")"
continue_count="$(jq -s '[.[] | select(.output.continue == true)] | length' "$events")"
scope_count="$(
  jq -s '
    [.[] | .input.turn_id | select(type == "string" and length > 0)]
    | unique
    | length
  ' "$events"
)"
[ "$block_count" -eq 3 ] && [ "$continue_count" -ge 3 ] && [ "$scope_count" -eq 3 ] || {
  echo "FAIL: unexpected hook events: block=$block_count continue=$continue_count scopes=$scope_count" >&2
  exit 1
}

hook_prompt_record_count="$(
  jq -s '
    [.[] | select(
      .type? == "response_item"
      and .payload.type? == "message"
      and ((.payload.content // []) | tostring | contains("<hook_prompt"))
    )
    ]
    | length
  ' "$rollout"
)"
# `codex resume` may serialize an additional history replay record without an
# ID. Only actual string IDs participate in the API ID contract.
hook_prompt_id_count="$(
  jq -s '
    [.[] | select(
      .type? == "response_item"
      and .payload.type? == "message"
      and ((.payload.content // []) | tostring | contains("<hook_prompt"))
      and ((.payload.id? | type) == "string")
    )
    | .payload.id]
    | unique
    | length
  ' "$rollout"
)"
bad_hook_id_count="$(
  jq -s '
    [.[] | select(
      .type? == "response_item"
      and .payload.type? == "message"
      and ((.payload.content // []) | tostring | contains("<hook_prompt"))
      and ((.payload.id? | type) == "string")
      and (.payload.id | startswith("msg_") | not)
    )
    ]
    | length
  ' "$rollout"
)"
bare_uuid_count="$(
  jq -s '
    [..
      | objects
      | select(
          .type? == "response_item"
          and .payload.type? == "message"
          and (.payload.id? | type) == "string"
          and (.payload.id | test("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"))
        )
    ]
    | length
  ' "$rollout"
)"
invalid_id_count="$(
  {
    rg -o 'invalid_id_prefix' "$rollout" "$initial_log" "$resume_log" 2>/dev/null || true
  } | wc -l | tr -d ' '
)"

[ "$hook_prompt_record_count" -ge 3 ] &&
  [ "$hook_prompt_id_count" -eq 3 ] &&
  [ "$bad_hook_id_count" -eq 0 ] &&
  [ "$bare_uuid_count" -eq 0 ] &&
  [ "$invalid_id_count" -eq 0 ] || {
    echo "FAIL: rollout audit hook_prompt_records=$hook_prompt_record_count hook_prompt_ids=$hook_prompt_id_count bad_hook_ids=$bad_hook_id_count bare_uuid=$bare_uuid_count invalid_id_prefix=$invalid_id_count" >&2
    exit 1
  }

for token in \
  "$primary_token" "$same_token" "$resume_token" \
  "$primary_hook_token" "$same_hook_token" "$resume_hook_token"; do
  rg -q --fixed-strings "$token" "$rollout" || {
    echo "FAIL: expected assistant token missing from rollout: $token" >&2
    exit 1
  }
done

echo "PASS: Codex $codex_version TUI Stop Hook initial/same-session/resume regression"
