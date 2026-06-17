#!/usr/bin/env bash
# 启动录制代理（reverse 模式）：Claude Code 经 base_url 重定向到本代理，
# 代理用合法证书转发到 api.anthropic.com，同时录制 /v1/messages 全量 I/O。
set -e
cd "$(dirname "$0")"

export CAPTURE_OUT="${CAPTURE_OUT:-$(pwd)/out/raw_turns}"
export IDLE_FLUSH_SEC="${IDLE_FLUSH_SEC:-90}"

cat <<EOF
[1/2] 启动 mitmproxy reverse → api.anthropic.com （监听 :8080）
      落盘目录: ${CAPTURE_OUT}
      空闲超时: ${IDLE_FLUSH_SEC}s（超时自动 flush；Ctrl+C 退出也会 flush）

[2/2] 新开终端，让 Claude Code 走代理后执行真实任务：
      ANTHROPIC_BASE_URL=http://127.0.0.1:8080 claude

      任务做完后静待 ${IDLE_FLUSH_SEC}s 自动落盘，或直接 Ctrl+C 本代理。
      随后转换：  python transform/to_section4_1.py
EOF
echo "---------------------------------------------------------------"
exec mitmdump --mode reverse:https://api.anthropic.com -s proxy/recorder.py
