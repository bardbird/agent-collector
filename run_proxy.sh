#!/usr/bin/env bash
# 启动录制代理（reverse 模式）：Claude Code 经 base_url 重定向到本代理，
# 代理用合法证书转发到配置的上游，同时录制 /v1/messages 全量 I/O。
set -euo pipefail
cd "$(dirname "$0")"

export CAPTURE_OUT="${CAPTURE_OUT:-$(pwd)/out/raw_turns}"
export IDLE_FLUSH_SEC="${IDLE_FLUSH_SEC:-90}"
if [[ -x ".venv/bin/mitmdump" ]]; then
  MITMDUMP_BIN=".venv/bin/mitmdump"
else
  MITMDUMP_BIN="${MITMDUMP_BIN:-mitmdump}"
fi

CLAUDE_SETTINGS_BASE_URL="$(
  python3 - <<'PY' 2>/dev/null || true
import json
from pathlib import Path

for path in (Path.home() / ".claude/settings.local.json", Path.home() / ".claude/settings.json"):
    if not path.exists():
        continue
    try:
        data = json.loads(path.read_text())
    except Exception:
        continue
    value = (data.get("env") or {}).get("ANTHROPIC_BASE_URL")
    if value:
        print(value)
        break
PY
)"
UPSTREAM="${UPSTREAM:-${ANTHROPIC_BASE_URL:-${CLAUDE_SETTINGS_BASE_URL:-https://api.anthropic.com}}}"
UPSTREAM_HOST="$(python3 -c "from urllib.parse import urlsplit;u=urlsplit('$UPSTREAM');print(f'{u.scheme}://{u.netloc}')" 2>/dev/null || echo "$UPSTREAM")"
UPSTREAM_PATH="$(python3 -c "from urllib.parse import urlsplit;u=urlsplit('$UPSTREAM');print(u.path.rstrip('/'))" 2>/dev/null || echo "")"
export UPSTREAM_PATH_PREFIX="$UPSTREAM_PATH"

cat <<EOF
[1/2] 启动 mitmproxy reverse → ${UPSTREAM} （监听 :8080）
      落盘目录: ${CAPTURE_OUT}
      空闲超时: ${IDLE_FLUSH_SEC}s（超时自动 flush；Ctrl+C 退出也会 flush）

[2/2] 新开终端，让 Claude Code 走代理后执行真实任务：
      ANTHROPIC_BASE_URL=http://127.0.0.1:8080${UPSTREAM_PATH} claude

      任务做完后静待 ${IDLE_FLUSH_SEC}s 自动落盘，或直接 Ctrl+C 本代理。
      随后转换：  python transform/to_section4_1.py
EOF
echo "---------------------------------------------------------------"
exec "$MITMDUMP_BIN" --mode "reverse:${UPSTREAM_HOST}" -s proxy/recorder.py
