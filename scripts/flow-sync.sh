#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-.}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

python3 "$SKILL_DIR/scripts/sync-project.py" "$SKILL_DIR" "$TARGET_DIR"
echo "💡 [project-flow-az] 成功为 $TARGET_DIR 热同步至 $(cat "$SKILL_DIR/VERSION" 2>/dev/null || echo 'v2.1.0')！"
