#!/usr/bin/env bash
#
# start.sh — Claude Code 轨迹采集代理 · 一键启动
#
# 做:依赖检查 → 目录初始化 → 端口检查 → 启动 reverse 代理(录制 /v1/messages)
#
# 用法:
#   ./start.sh                  前台启动(默认),Ctrl+C 退出即 flush 落盘
#   ./start.sh -d               后台启动(daemon),日志写 out/proxy.log
#   ./start.sh stop             停止后台代理
#   ./start.sh status           查看代理状态
#   ./start.sh restart          重启后台代理
#   ./start.sh transform        把已采集的 raw_turns 转成 §4.1 JSONL
#   ./start.sh -p 9090          指定端口(默认 8080)
#   ./start.sh --no-install     跳过依赖自动安装
#
# 启动后,让 Claude Code 走代理执行真实任务:
#   ANTHROPIC_BASE_URL=http://127.0.0.1:<port> claude

set -euo pipefail
IFS=$'\n\t'

# ---------------- 颜色 ----------------
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
  C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'; C_GRAY=$'\033[90m'
else
  C_RESET=""; C_BOLD=""; C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_GRAY=""
fi
info() { printf "${C_CYAN}▶${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}!${C_RESET} %s\n" "$*"; }
err()  { printf "${C_RED}✗${C_RESET} %s\n" "$*" >&2; }
die()  { err "$*"; exit 1; }

# ---------------- 路径 ----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
ADDON="proxy/recorder.py"
OUT_DIR="out"
RAW_DIR="${OUT_DIR}/raw_turns"
JSONL_DIR="${OUT_DIR}/jsonl"
IMG_DIR="${OUT_DIR}/images"
LOG_FILE="${OUT_DIR}/proxy.log"
PID_FILE="${OUT_DIR}/.proxy.pid"

# ---------------- 默认参数 ----------------
PORT="${PORT:-8080}"
# 上游:优先 UPSTREAM / ANTHROPIC_BASE_URL 环境变量,回退官方端点(适配自定义网关,如 bigmodel)
UPSTREAM="${UPSTREAM:-${ANTHROPIC_BASE_URL:-https://api.anthropic.com}}"
# mitmproxy reverse 不接受 path,故拆分:host 进 reverse mode,path 拼回 claude 的 BASE_URL
UPSTREAM_HOST="$(python3 -c "from urllib.parse import urlsplit;u=urlsplit('$UPSTREAM');print(f'{u.scheme}://{u.netloc}')" 2>/dev/null || echo "$UPSTREAM")"
UPSTREAM_PATH="$(python3 -c "from urllib.parse import urlsplit;u=urlsplit('$UPSTREAM');print(u.path.rstrip('/'))" 2>/dev/null || echo "")"
export UPSTREAM_PATH_PREFIX="$UPSTREAM_PATH"   # recorder 用:补客户端缺失的 path 前缀
MODE="foreground"
NO_INSTALL=0
ACTION="start"

# ---------------- 参数解析 ----------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--daemon)  MODE="background"; shift;;
    -p|--port)    PORT="${2:?--port 需要值}"; shift 2;;
    --no-install) NO_INSTALL=1; shift;;
    stop)     ACTION="stop"; shift;;
    status)   ACTION="status"; shift;;
    restart)  ACTION="restart"; shift;;
    transform) ACTION="transform"; shift;;
    dash|dashboard) ACTION="dash"; shift;;
    all) ACTION="all"; shift;;
    capture) ACTION="capture"; shift;;
    -h|--help) ACTION="help"; shift;;
    *) die "未知参数: $1(用 -h 查看帮助)";;
  esac
done

# ---------------- 公共函数 ----------------
show_help() {
  cat <<'EOF'
start.sh — Claude Code 轨迹采集代理 · 一键启动

用法:
  ./start.sh                  前台启动(默认),Ctrl+C 退出即 flush 落盘
  ./start.sh -d               后台启动(daemon),日志写 out/proxy.log
  ./start.sh stop             停止后台代理
  ./start.sh status           查看代理状态
  ./start.sh restart          重启后台代理
  ./start.sh all              一键启动(后台采集代理 + 前台可视化面板)
  ./start.sh capture          用 --settings 启动采集 claude(只覆盖 BASE_URL)
  ./start.sh transform        把已采集的 raw_turns 转成 §4.1 JSONL
  ./start.sh dash             启动可视化面板(查看采集情况)
  ./start.sh -p 9090          指定端口(默认 8080)
  ./start.sh --no-install     跳过依赖自动安装

启动后,让 Claude Code 走代理执行真实任务:
  ANTHROPIC_BASE_URL=http://127.0.0.1:<port> claude
EOF
}

ensure_dirs() { mkdir -p "$RAW_DIR" "$JSONL_DIR" "$IMG_DIR"; }

port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

pid_alive() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null
}

ensure_deps() {
  command -v python3 >/dev/null 2>&1 || die "未找到 python3,请先安装 Python 3。"
  if command -v mitmdump >/dev/null 2>&1; then
    ok "mitmproxy 已就绪: $(command -v mitmdump)"; return
  fi
  if [[ $NO_INSTALL -eq 1 ]]; then
    err "未找到 mitmdump 且 --no-install 已指定。手动安装其一:"
    err "  brew install mitmproxy"; err "  pipx install mitmproxy"; err "  pip3 install --user mitmproxy"
    exit 1
  fi
  warn "未找到 mitmproxy,尝试自动安装…"
  if   command -v brew >/dev/null 2>&1; then brew install mitmproxy || true
  elif command -v pipx >/dev/null 2>&1; then pipx install mitmproxy || true
  else pip3 install --user mitmproxy || true
  fi
  command -v mitmdump >/dev/null 2>&1 || {
    err "自动安装失败。手动安装其一:"
    err "  brew install mitmproxy"; err "  pipx install mitmproxy"; exit 1
  }
  ok "mitmproxy 安装完成: $(command -v mitmdump)"
}

# ---------------- 动作 ----------------
do_status() {
  if pid_alive; then
    ok "代理运行中 · PID $(cat "$PID_FILE") · 端口 ${PORT} · 日志 ${LOG_FILE}"
  elif port_in_use "$PORT"; then
    warn "端口 ${PORT} 被其他进程占用(非本脚本管理)"
  else
    info "代理未运行"
  fi
}

do_stop() {
  if pid_alive; then
    local pid; pid="$(cat "$PID_FILE")"
    info "停止代理 PID ${pid}(SIGTERM,触发 recorder flush)…"
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      warn "未响应 TERM,发送 KILL"; kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    ok "已停止"
  else
    rm -f "$PID_FILE"
    info "没有运行中的后台代理"
  fi
}

do_transform() {
  ensure_dirs
  python3 transform/to_section4_1.py --in "$RAW_DIR" --out "$JSONL_DIR" --images "$IMG_DIR"
}

print_banner() {
  echo
  printf "${C_BOLD}${C_CYAN}━━━ Claude Code 轨迹采集代理 ━━━${C_RESET}\n"
  printf "  模式:      %s\n" "$([[ $MODE == background ]] && echo '后台(daemon)' || echo '前台')"
  printf "  监听:      ${C_GREEN}http://127.0.0.1:%s${C_RESET}  → reverse %s\n" "$PORT" "$UPSTREAM"
  printf "  落盘:      %s\n" "$RAW_DIR/"
  printf "  空闲 flush: %ss\n" "${IDLE_FLUSH_SEC:-90}"
  echo
  printf "${C_BOLD}下一步 — 让 Claude Code 走代理执行真实任务:${C_RESET}\n"
  printf "  ${C_GREEN}ANTHROPIC_BASE_URL=http://127.0.0.1:%s claude${C_RESET}\n" "$PORT"
  echo  "  任务做完:  前台 Ctrl+C  /  后台 ./$0 stop   → 触发落盘"
  printf "  转 §4.1:   ${C_GREEN}./%s transform${C_RESET}\n" "$(basename "$0")"
  echo
  printf "${C_GRAY}(reverse 模式:Claude Code 走本地 HTTP,无需信任 mitmproxy CA)${C_RESET}\n"
  echo
}

do_start() {
  ensure_dirs
  ensure_deps
  [[ -f "$ADDON" ]] || die "找不到代理 addon: $ADDON"

  if pid_alive; then
    warn "已有后台代理在运行(PID $(cat "$PID_FILE"))。如需重启: $0 restart"
    exit 0
  fi
  if port_in_use "$PORT"; then
    die "端口 ${PORT} 已被占用。换端口: $0 -p <port>"
  fi

  export CAPTURE_OUT="${SCRIPT_DIR}/${RAW_DIR}"
  export IDLE_FLUSH_SEC="${IDLE_FLUSH_SEC:-90}"

  print_banner

  # addon 路径用绝对值,后台运行时更稳
  local args=( --mode "reverse:${UPSTREAM_HOST}" -s "${SCRIPT_DIR}/${ADDON}" -p "$PORT" )

  if [[ "$MODE" == "background" ]]; then
    nohup mitmdump "${args[@]}" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    # 等待监听就绪或进程退出
    for _ in $(seq 1 40); do
      if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        err "后台启动失败,日志尾部:"
        tail -n 20 "$LOG_FILE" >&2 || true
        exit 1
      fi
      port_in_use "$PORT" && break
      sleep 0.25
    done
    ok "后台启动成功 · PID ${pid} · 日志 ${LOG_FILE}"
  else
    info "前台启动(Ctrl+C 退出即 flush)"
    exec mitmdump "${args[@]}"
  fi
}

start_proxy_bg() {
  # 后台启动采集代理。前置:已 ensure_dirs / ensure_deps。
  if pid_alive; then
    warn "已有后台代理运行(PID $(cat "$PID_FILE")),复用"; return 0
  fi
  if port_in_use "$PORT"; then
    die "端口 ${PORT} 已被占用。换端口: $0 -p <port>"
  fi
  export CAPTURE_OUT="${SCRIPT_DIR}/${RAW_DIR}"
  export IDLE_FLUSH_SEC="${IDLE_FLUSH_SEC:-90}"
  local args=( --mode "reverse:${UPSTREAM_HOST}" -s "${SCRIPT_DIR}/${ADDON}" -p "$PORT" )
  nohup mitmdump "${args[@]}" > "$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  for _ in $(seq 1 40); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$PID_FILE"
      err "代理后台启动失败,日志尾部:"; tail -n 20 "$LOG_FILE" >&2 || true
      return 1
    fi
    port_in_use "$PORT" && return 0
    sleep 0.25
  done
  return 0
}

do_all() {
  ensure_dirs
  ensure_deps
  [[ -f "$ADDON" ]] || die "找不到代理 addon: $ADDON"
  command -v python3 >/dev/null 2>&1 || die "需要 python3"
  local dport="${DASH_PORT:-8765}"

  echo
  printf "${C_BOLD}${C_CYAN}━━━ 一键启动:采集代理 + 可视化面板 ━━━${C_RESET}\n"
  info "后台启动采集代理(端口 ${PORT})…"
  start_proxy_bg || die "代理启动失败"
  ok "采集代理已运行 · PID $(cat "$PID_FILE") · 日志 ${LOG_FILE}"
  echo
  printf "  面板:  ${C_GREEN}http://127.0.0.1:%s${C_RESET}  (5s 自动刷新)\n" "$dport"
  printf "  采集:  ${C_GREEN}ANTHROPIC_BASE_URL=http://127.0.0.1:%s claude${C_RESET}\n" "$PORT"
  echo  "  退出:  Ctrl+C 停止面板并自动停止后台代理"
  echo

  # 面板前台运行;任何方式退出面板 → 一并停止后台代理
  trap 'echo; info "面板退出,停止后台代理…"; do_stop || true' EXIT
  python3 "${SCRIPT_DIR}/dashboard/server.py" -p "$dport"
}

do_capture() {
  command -v python3 >/dev/null 2>&1 || die "需要 python3"
  command -v claude >/dev/null 2>&1 || die "未找到 claude"

  if ! pid_alive && ! port_in_use "$PORT"; then
    warn "采集代理未运行,请先在另一终端执行: ./start.sh 或 ./start.sh all"
  fi

  local cap_settings="${SCRIPT_DIR}/out/capture.settings.json"
  mkdir -p "${SCRIPT_DIR}/out"
  # 已实测 --settings 为 deep merge:本文件只覆盖 BASE_URL,
  # token/模型/plugins/skills 全从全局 settings 继承 → 本文件无任何敏感字段
  python3 - "$cap_settings" "$PORT" "$UPSTREAM_PATH" <<'PY'
import json, sys
dst, port, path = sys.argv[1], sys.argv[2], sys.argv[3]
json.dump({"env": {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}{path}"}},
          open(dst, "w"), ensure_ascii=False, indent=2)
print(f"[capture] {dst}  (BASE_URL=http://127.0.0.1:{port}{path},无敏感字段)")
PY

  echo
  printf "${C_BOLD}${C_CYAN}━━━ 隔离采集 Claude Code(--settings)━━━${C_RESET}\n"
  printf "  采集 settings: %s\n" "$cap_settings"
  printf "  BASE_URL:      ${C_GREEN}http://127.0.0.1:%s%s${C_RESET} → reverse %s\n" "$PORT" "$UPSTREAM_PATH" "$UPSTREAM_HOST"
  printf "  ${C_GRAY}(只覆盖 BASE_URL;token/模型/plugins/skills 沿用全局,不污染你的配置)${C_RESET}\n"
  echo
  info "启动采集 claude(Ctrl+C 退出)…"
  exec claude --settings "$cap_settings"
}

do_dash() {
  ensure_dirs
  command -v python3 >/dev/null 2>&1 || die "需要 python3"
  local dport="${DASH_PORT:-8765}"
  echo
  printf "${C_BOLD}${C_CYAN}━━━ 采集情况可视化面板 ━━━${C_RESET}\n"
  printf "  地址:  ${C_GREEN}http://127.0.0.1:%s${C_RESET}\n" "$dport"
  printf "  数据:  %s\n" "$RAW_DIR/"
  printf "  ${C_GRAY}(自动刷新 5s;Ctrl+C 退出)${C_RESET}\n"
  echo
  exec python3 "${SCRIPT_DIR}/dashboard/server.py" -p "$dport"
}

case "$ACTION" in
  start)     do_start;;
  stop)      do_stop;;
  status)    do_status;;
  restart)   do_stop; do_start;;
  transform) do_transform;;
  dash|dashboard) do_dash;;
  all)        do_all;;
  capture)    do_capture;;
  help)      show_help;;
esac
