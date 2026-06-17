"""
dashboard/server.py — 采集情况可视化服务(零额外依赖,仅标准库)

端点:
  GET  /                 → index.html
  GET  /api/stats        → 采集概览(任务数/轮次/消息/工具调用/代理状态/最近时间)
  GET  /api/tasks        → 任务列表(摘要,按时间倒序)
  GET  /api/task/<id>    → 单任务完整数据(Anthropic 中间格式)
  POST /api/transform    → 触发 to_section4_1.py 转化

运行:
  python3 dashboard/server.py            # 默认 :8765
  python3 dashboard/server.py -p 9000
  DASH_PORT=9000 ./start.sh dash         # 经 start.sh 启动
"""
import json
import os
import sys
import subprocess
import argparse
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent            # poc/
RAW_DIR = ROOT / "out" / "raw_turns"
JSONL_DIR = ROOT / "out" / "jsonl"
IMG_DIR = ROOT / "out" / "images"
PID_FILE = ROOT / "out" / ".proxy.pid"
INDEX = Path(__file__).resolve().parent / "index.html"
TRANSFORM = ROOT / "transform" / "to_section4_1.py"


def proxy_running():
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)          # 0 = 探活,不发信号
        return True
    except Exception:
        return False


def _is_list(x):
    return isinstance(x, list)


def summarize(rec, fname, mtime):
    """从 Anthropic 中间格式抽取摘要。"""
    msgs = rec.get("messages", []) or []
    out_blocks = rec.get("assistant_output", []) or []
    tools = set()
    tool_calls = 0

    for m in msgs:
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if not _is_list(c):
            continue
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                tool_calls += 1
                if b.get("name"):
                    tools.add(b["name"])
    for b in out_blocks:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            tool_calls += 1
            if b.get("name"):
                tools.add(b["name"])

    has_image = any(
        m.get("role") == "user" and _is_list(m.get("content")) and any(
            isinstance(b, dict) and b.get("type") == "image" for b in m["content"]
        )
        for m in msgs
    )

    return {
        "task_id": rec.get("task_id", Path(fname).stem),
        "turn_count": rec.get("turn_count"),
        "msg_count": len(msgs),
        "tool_call_count": tool_calls,
        "tools_used": sorted(tools),
        "has_system": bool(rec.get("system")),
        "has_image": has_image,
        "model": rec.get("model"),
        "captured_at": rec.get("captured_at") or int(mtime),
        "file": fname,
    }


def load_all_summaries():
    items = []
    if not RAW_DIR.exists():
        return items
    for f in sorted(RAW_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(f.read_text())
        except Exception:
            continue
        items.append(summarize(rec, f.name, f.stat().st_mtime))
    return items


def stats():
    sums = load_all_summaries()
    return {
        "task_count": len(sums),
        "total_turns": sum((s["turn_count"] or 0) for s in sums),
        "total_messages": sum(s["msg_count"] for s in sums),
        "total_tool_calls": sum(s["tool_call_count"] for s in sums),
        "latest_at": max((s["captured_at"] for s in sums), default=0),
        "proxy_running": proxy_running(),
        "raw_dir": str(RAW_DIR),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._send(INDEX.read_bytes(), "text/html; charset=utf-8")
        if p == "/api/stats":
            return self._json(stats())
        if p == "/api/tasks":
            return self._json(load_all_summaries())
        if p.startswith("/api/task/"):
            tid = p[len("/api/task/"):]
            f = RAW_DIR / f"{tid}.json"
            if f.exists():
                try:
                    return self._json(json.loads(f.read_text()))
                except Exception as e:
                    return self._json({"error": str(e)}, 500)
            return self._json({"error": "not found"}, 404)
        self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/transform":
            try:
                out = subprocess.run(
                    [sys.executable, str(TRANSFORM),
                     "--in", str(RAW_DIR), "--out", str(JSONL_DIR),
                     "--images", str(IMG_DIR)],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
                return self._json({
                    "ok": out.returncode == 0,
                    "stdout": out.stdout.strip(),
                    "stderr": out.stderr.strip(),
                })
            except Exception as e:
                return self._json({"ok": False, "stderr": str(e)}, 500)
        self.send_error(404)

    def log_message(self, *a):
        pass   # 静默访问日志


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--port", type=int, default=8765)
    a = ap.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"[dashboard] http://127.0.0.1:{a.port}   (raw: {RAW_DIR})")
    print(f"[dashboard] proxy running: {proxy_running()}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[dashboard] stopped")


if __name__ == "__main__":
    main()
