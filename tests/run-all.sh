#!/usr/bin/env bash
# 一次性跑完全部回归，避免逐条命令拼写差异带来的漏跑。
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
python3 -m py_compile "$ROOT"/scripts/*.py || fail=1
for t in "$ROOT"/tests/test-*.py; do
  printf "%-44s " "$(basename "$t")"
  if python3 "$t" >/tmp/pf-test.log 2>&1; then
    echo PASS
  else
    echo FAIL
    tail -8 /tmp/pf-test.log
    fail=1
  fi
done
printf "%-44s " "test-multi-project-structure.sh"
if bash "$ROOT/tests/test-multi-project-structure.sh" >/tmp/pf-test2.log 2>&1; then
  echo PASS
else
  echo FAIL
  tail -8 /tmp/pf-test2.log
  fail=1
fi
exit "$fail"
