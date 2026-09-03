#!/usr/bin/env bash
set -euo pipefail

# 从仓库根目录执行：初始化 WikiSkill 并挂载到 Codex / Claude Code。
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills"
CLAUDE_SKILLS="$ROOT/.claude/skills"
SOURCE="$ROOT/skills/wikiskill"

[ -f "$ROOT/wikiskill/cli/main.py" ] || { echo "错误：请从包含 wikiskill/ 的仓库运行此脚本。" >&2; exit 1; }
[ -d "$SOURCE" ] || { echo "错误：缺少 $SOURCE" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "错误：需要 Python 3.10+。" >&2; exit 1; }
python3 - "$ROOT" <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("错误：WikiSkill 需要 Python 3.10+。")
PY

mkdir -p "$CODEX_SKILLS" "$CLAUDE_SKILLS"
mount() {
  local target="$1"
  if [ -e "$target" ] || [ -L "$target" ]; then
    [ -d "$target" ] && [ "$(cd "$target" && pwd -P)" = "$SOURCE" ] || {
      echo "错误：目标已存在且不是当前 WikiSkill 软链：$target" >&2
      exit 1
    }
  else
    ln -s "$SOURCE" "$target"
  fi
  echo "已挂载：$target"
}

PYTHONPATH="$ROOT" python3 -m wikiskill.cli --workspace "$ROOT" init
mount "$CODEX_SKILLS/wikiskill"
mount "$CLAUDE_SKILLS/wikiskill"
PYTHONPATH="$ROOT" python3 -m wikiskill.cli --workspace "$ROOT" status
echo "WikiSkill 安装、初始化和双端挂载完成。"
