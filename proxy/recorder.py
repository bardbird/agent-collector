"""
recorder.py — mitmproxy addon（reverse 代理模式）

拦截 Claude Code ↔ api.anthropic.com 的 POST /v1/messages 流量，
按任务(task_key)缓存"最近一次请求的完整 input + 本轮 assistant 输出"，
空闲超时(或退出)后落盘为 Anthropic 原始中间格式 JSON。

运行（见 ../run_proxy.sh）：
  mitmdump --mode reverse:https://api.anthropic.com -s recorder.py
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

from mitmproxy import http, ctx

OUT = Path(os.environ.get(
    "CAPTURE_OUT",
    str(Path(__file__).resolve().parent.parent / "out" / "raw_turns"),
))
OUT.mkdir(parents=True, exist_ok=True)

IDLE_FLUSH_SEC = int(os.environ.get("IDLE_FLUSH_SEC", "90"))
PATH = "/v1/messages"


class Task:
    def __init__(self, key):
        self.key = key
        self.last_input = None       # 最近一次请求的 messages（完整累积，Anthropic 格式）
        self.last_tools = None
        self.last_system = None
        self.last_model = None
        self.last_output = None      # 最近一次 assistant 输出（content blocks）
        self.turn_count = 0
        self.last_ts = time.time()


class Recorder:
    def __init__(self):
        self.tasks = {}              # key -> Task

    # ---------------- request ----------------
    def request(self, flow: http.HTTPFlow):
        if not flow.request.path.endswith(PATH):
            return
        try:
            body = json.loads(flow.request.text or "{}")
        except Exception:
            return
        msgs = body.get("messages", [])
        first_user = next((m for m in msgs if m.get("role") == "user"), {})
        key = hashlib.sha1(
            json.dumps(first_user, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]

        t = self.tasks.get(key)
        if t is None:
            t = Task(key)
            self.tasks[key] = t
        t.last_input = msgs
        t.last_tools = body.get("tools", [])
        t.last_system = body.get("system")
        t.last_model = body.get("model")
        t.turn_count += 1
        t.last_ts = time.time()
        flow.metadata["task_key"] = key

    # ---------------- response ----------------
    def response(self, flow: http.HTTPFlow):
        key = flow.metadata.get("task_key")
        if not key or key not in self.tasks:
            return
        t = self.tasks[key]
        t.last_output = self._parse_sse(flow.response.text or "")
        t.last_ts = time.time()
        ctx.log.info(
            f"[recorder] task {key} turn#{t.turn_count} "
            f"out_blocks={len(t.last_output)}"
        )
        self._flush_idle()

    # ---------------- SSE 累积 ----------------
    def _parse_sse(self, text):
        """把 Anthropic SSE 流拼成 content blocks 列表（text / tool_use / thinking）。"""
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
                idx = ev["index"]
                blocks[idx] = dict(ev["block"])
            elif tp == "content_block_delta":
                d = ev.get("delta", {})
                b = blocks.get(idx)
                if not b:
                    continue
                dt = d.get("type")
                if dt == "text_delta":
                    b["text"] = b.get("text", "") + d.get("text", "")
                elif dt == "input_json_delta":
                    b["_input_raw"] = b.get("_input_raw", "") + d.get("partial_json", "")
                elif dt == "thinking_delta":
                    b["thinking"] = b.get("thinking", "") + d.get("thinking", "")
            elif tp == "content_block_stop":
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

    def _flush(self, key, t):
        if not t.last_input or not t.last_output:
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
        }
        path = OUT / f"{key}.json"
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
        ctx.log.info(
            f"[recorder] FLUSH task {key} -> {path.name} "
            f"(turns={t.turn_count}, input_msgs={len(t.last_input)}, "
            f"out_blocks={len(t.last_output)})"
        )
        self.tasks.pop(key, None)

    def done(self):
        """mitmproxy 退出时兜底 flush 全部缓存任务。"""
        for key, t in list(self.tasks.items()):
            self._flush(key, t)


addons = [Recorder()]
