"""
recorder.py — mitmproxy addon（reverse 代理模式）

拦截 Claude Code ↔ 配置的 Anthropic-compatible 上游的 POST /v1/messages 流量，
按任务(task_key)缓存"最近一次请求的完整 input + 本轮 assistant 输出"，
空闲超时(或退出)后落盘为 Anthropic 原始中间格式 JSON。

运行（见 ../run_proxy.sh）：
  mitmdump --mode reverse:<upstream> -s recorder.py
  # 另一终端：
  ANTHROPIC_BASE_URL=http://127.0.0.1:8080 claude  <执行真实任务>

设计要点：
  · base_url 重定向路线，无需 TLS 证书，到上游仍是合法 HTTPS（mitmproxy 用合法证书连上游）。
  · 不开流式转发（默认缓冲），response hook 拿到完整 SSE 文本，录制最可靠；
    代价：Claude Code 每轮响应延迟感略增 —— 样例阶段可接受。
  · 利用 Anthropic messages 的【累积性】：某任务"最后一次请求的 input_messages +
    本轮 assistant 输出"即完整轨迹原料，无需逐轮拼接。
  · task_key 取首条 user message 的哈希：同一任务多轮请求，首条 user 稳定不变。
  · 只录 request/response body，不录 header（API Key 不会落盘）。
"""
import json
import time
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

from mitmproxy import http, ctx

OUT = Path(os.environ.get(
    "CAPTURE_OUT",
    str(Path(__file__).resolve().parent.parent / "out" / "raw_turns"),
))
OUT.mkdir(parents=True, exist_ok=True)
RAW_HTTP = Path(os.environ.get("CAPTURE_RAW_HTTP", str(OUT.parent / "raw_http")))
RAW_HTTP.mkdir(parents=True, exist_ok=True)

IDLE_FLUSH_SEC = int(os.environ.get("IDLE_FLUSH_SEC", "90"))
PATH = "/v1/messages"
# 上游 path 前缀(如 bigmodel 的 /api/anthropic);客户端未带时由 request hook 补上
PREFIX = os.environ.get("UPSTREAM_PATH_PREFIX", "")


class Task:
    def __init__(self, key):
        self.key = key
        self.last_input = None       # 最近一次请求的 messages（完整累积，Anthropic 格式）
        self.last_tools = None
        self.last_system = None
        self.last_model = None
        self.last_output = None      # 最近一次 assistant 输出（content blocks）
        self.last_request_text = None
        self.last_request_url = None
        self.last_response_text = None
        self.last_response_status = None
        self.last_response_headers = None
        self.turn_count = 0
        self.last_ts = time.time()


class Recorder:
    def __init__(self):
        self.tasks = {}              # key -> Task

    def _body_text(self, message):
        raw = message.raw_content
        if raw is None:
            raw = message.content or b""
        for enc in ("utf-8", "utf-8-sig"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                pass
        ctype = message.headers.get("content-type", "")
        if "charset=" in ctype:
            enc = ctype.rsplit("charset=", 1)[-1].split(";", 1)[0].strip()
            try:
                return raw.decode(enc)
            except Exception:
                pass
        return raw.decode("utf-8", errors="replace")

    def _path_query(self, path):
        u = urlsplit(path)
        return u.path, (("?" + u.query) if u.query else "")

    # ---------------- request ----------------
    def request(self, flow: http.HTTPFlow):
        req_path, query = self._path_query(flow.request.path)
        # 补上游 path 前缀:交互式 Claude Code 某些请求未拼 BASE_URL 的 path,
        # 直接发 /v1/messages;此处统一补成 <prefix>/v1/messages 再转发
        if PREFIX and req_path.startswith("/v1/") and not req_path.startswith(PREFIX):
            flow.request.path = PREFIX + req_path + query
            req_path = PREFIX + req_path
        if not req_path.endswith(PATH):
            return
        raw_request_text = self._body_text(flow.request)
        try:
            body = json.loads(raw_request_text or "{}")
        except Exception:
            body = {}
        msgs = body.get("messages", [])
        first_user = next((m for m in msgs if m.get("role") == "user"), {})
        key_source = first_user if first_user else raw_request_text
        key = hashlib.sha1(
            json.dumps(key_source, sort_keys=True, ensure_ascii=False).encode()
            if not isinstance(key_source, str)
            else key_source.encode()
        ).hexdigest()[:16]

        t = self.tasks.get(key)
        if t is None:
            t = Task(key)
            self.tasks[key] = t
        t.last_input = msgs
        t.last_tools = body.get("tools", [])
        t.last_system = body.get("system")
        t.last_model = body.get("model")
        t.last_request_text = raw_request_text
        t.last_request_url = flow.request.pretty_url
        t.turn_count += 1
        t.last_ts = time.time()
        flow.metadata["task_key"] = key

    # ---------------- response ----------------
    def response(self, flow: http.HTTPFlow):
        key = flow.metadata.get("task_key")
        if not key or key not in self.tasks:
            return
        t = self.tasks[key]
        t.last_response_text = self._body_text(flow.response)
        t.last_response_status = flow.response.status_code
        t.last_response_headers = dict(flow.response.headers)
        try:
            t.last_output = self._parse_sse(t.last_response_text)
        except Exception as e:
            ctx.log.warn(f"[recorder] parse failed for task {key}: {e}")
            t.last_output = []
        t.last_ts = time.time()
        ctx.log.info(
            f"[recorder] task {key} turn#{t.turn_count} "
            f"out_blocks={len(t.last_output)}"
        )
        self._flush(key, t, keep=True)   # 每轮增量 flush,面板近实时可见
        self._flush_idle()

    # ---------------- SSE 累积 ----------------
    def _parse_sse(self, text):
        """把 Anthropic SSE 流拼成 content blocks 列表（text / tool_use / thinking）。"""
        try:
            obj = json.loads(text or "{}")
            content = obj.get("content")
            if isinstance(content, list):
                return content
        except Exception:
            pass

        blocks = {}
        idx = -1
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            tp = ev.get("type")
            if tp == "content_block_start":
                idx = ev.get("index", len(blocks))
                block = ev.get("block") or ev.get("content_block")
                if not isinstance(block, dict):
                    block = {"type": ev.get("block_type") or ev.get("content_type") or "text"}
                    for k in ("id", "name", "text", "input", "thinking"):
                        if k in ev:
                            block[k] = ev[k]
                if block.get("type") == "text":
                    block.setdefault("text", "")
                blocks[idx] = dict(block)
            elif tp == "content_block_delta":
                idx = ev.get("index", idx)
                d = ev.get("delta", {})
                b = blocks.get(idx)
                if not b:
                    b = {"type": "text", "text": ""}
                    blocks[idx] = b
                dt = d.get("type")
                if dt == "text_delta":
                    b.setdefault("type", "text")
                    b["text"] = b.get("text", "") + d.get("text", "")
                elif dt == "input_json_delta":
                    if b.get("type") == "text":
                        b["type"] = "tool_use"
                    b["_input_raw"] = b.get("_input_raw", "") + d.get("partial_json", "")
                elif dt == "thinking_delta":
                    if b.get("type") == "text":
                        b["type"] = "thinking"
                    b["thinking"] = b.get("thinking", "") + d.get("thinking", "")
            elif tp == "content_block_stop":
                idx = ev.get("index", idx)
                b = blocks.get(idx)
                if b and "_input_raw" in b:
                    try:
                        b["input"] = json.loads(b["_input_raw"])
                    except Exception:
                        b["input"] = {}
                    b.pop("_input_raw", None)
        return [blocks[i] for i in sorted(blocks)]

    # ---------------- flush ----------------
    def _flush_idle(self):
        now = time.time()
        for key, t in list(self.tasks.items()):
            if now - t.last_ts > IDLE_FLUSH_SEC:
                self._flush(key, t)

    def _flush(self, key, t, keep=False):
        if not t.last_input:
            if not keep:
                self.tasks.pop(key, None)
            return
        rec = {
            "task_id": key,
            "model": t.last_model,
            "system": t.last_system,
            "tools": t.last_tools,
            "messages": t.last_input,           # 完整累积历史（Anthropic 格式）
            "assistant_output": t.last_output,  # 最终轮 assistant blocks
            "turn_count": t.turn_count,
            "captured_at": int(t.last_ts),
            "raw": {
                "request": {
                    "url": t.last_request_url,
                    "body": t.last_request_text,
                },
                "response": {
                    "status_code": t.last_response_status,
                    "headers": t.last_response_headers,
                    "body": t.last_response_text,
                },
            },
        }
        path = OUT / f"{key}.json"
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
        raw_base = RAW_HTTP / f"{key}_turn{t.turn_count:03d}"
        req_path = raw_base.with_suffix(".request.txt")
        resp_path = raw_base.with_suffix(".response.txt")
        meta_path = raw_base.with_suffix(".meta.json")
        req_path.write_text(t.last_request_text or "")
        resp_path.write_text(t.last_response_text or "")
        meta_path.write_text(json.dumps({
            "task_id": key,
            "turn_count": t.turn_count,
            "captured_at": int(t.last_ts),
            "request": {
                "url": t.last_request_url,
                "body_file": req_path.name,
            },
            "response": {
                "status_code": t.last_response_status,
                "headers": t.last_response_headers,
                "body_file": resp_path.name,
            },
        }, ensure_ascii=False, indent=2))
        ctx.log.info(
            f"[recorder] FLUSH task {key} -> {path.name} "
            f"(turns={t.turn_count}, input_msgs={len(t.last_input)}, "
            f"out_blocks={len(t.last_output)}, raw={meta_path.name})"
        )
        if not keep:
            self.tasks.pop(key, None)

    def done(self):
        """mitmproxy 退出时兜底 flush 全部缓存任务。"""
        for key, t in list(self.tasks.items()):
            self._flush(key, t)


addons = [Recorder()]
