"""mock/mock_server.py — §C.2 Mock 回放服务。

启动: python mock/mock_server.py --data mock/mock_responses.jsonl --port 8080
接口: POST /mock/<tool_name>  body: {"arguments": {...}}
索引: sha256(tool_name + json.dumps(arguments, sort_keys=True))
未命中: 404 + {"error": "no mock found", "request_hash": "..."}

依赖标准库,无第三方包。
"""
from __future__ import annotations
import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def request_hash(tool_name: str, arguments: dict) -> str:
    raw = tool_name + json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_db(path: Path) -> dict:
    db = {}
    if not path.exists():
        return db
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        rec = json.loads(ln)
        key = rec.get("request_hash") or request_hash(
            rec.get("tool_name", ""), rec.get("request", {}))
        db[key] = rec
    return db


def make_handler(db: dict):
    class H(BaseHTTPRequestHandler):
        def _reply(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self.path.startswith("/mock/"):
                return self._reply(404, {"error": "unknown path"})
            tool_name = self.path[len("/mock/"):]
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._reply(400, {"error": "invalid json body"})
            args = body.get("arguments", {})
            key = request_hash(tool_name, args)
            rec = db.get(key)
            if not rec:
                return self._reply(404, {"error": "no mock found",
                                         "tool_name": tool_name,
                                         "request_hash": key})
            return self._reply(200, rec.get("response", {}))

        def log_message(self, *_a):
            pass
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="mock/mock_responses.jsonl")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    db = load_db(Path(a.data))
    print(f"[mock] loaded {len(db)} record(s) from {a.data}")
    print(f"[mock] listening on http://127.0.0.1:{a.port}/mock/<tool>")
    HTTPServer(("127.0.0.1", a.port), make_handler(db)).serve_forever()


if __name__ == "__main__":
    main()
