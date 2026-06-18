"""
transform/common.py — §5.1–§5.9 转化器的共用层。

只做"忠实搬运 + 规则校验",不构造内容。所有分项子命令(to_section_5_x.py)
依赖本模块完成:
  1. Anthropic 原始 → §4.1 OpenAI FC 格式 (anthropic_to_openai)
  2. §4.1 schema 静态校验           (validate_4_1)
  3. §4.4 红线/反模式校验            (validate_4_4)
  4. 多样性统计                       (diversity_report)
  5. meta 字段注入                    (inject_meta)
  6. 图片落盘                         (extract_images)

校验失败的记录:由子命令决定是落 _rejected.jsonl 还是抛错。本模块不替子命令做策略决定。
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------- I/O ----------

def load_raw(p: Path) -> Dict[str, Any]:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load_sidecar(raw_path: Path) -> Dict[str, Any]:
    sidecar = raw_path.with_suffix(".gt.json")
    if not sidecar.exists():
        return {}
    return json.loads(sidecar.read_text(encoding="utf-8"))


def dump_jsonl(obj: Dict[str, Any], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def reset_file(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()


# ---------- 图片落盘 ----------

def extract_images(blocks: List[Dict[str, Any]],
                   img_dir: Path,
                   rel_prefix: str) -> List[Dict[str, Any]]:
    """把 user content 里的 Anthropic image block 转成 §4.1 image_url 片段。
    base64 图片落盘到 img_dir/,文件名 = sha1(data)[:16].ext。"""
    img_dir.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for b in blocks:
        t = b.get("type")
        if t == "text":
            out.append({"type": "text", "text": b.get("text", "")})
        elif t == "image":
            src = b.get("source", {})
            data = src.get("data")
            if not data:
                continue
            ext = (src.get("media_type") or "image/png").split("/")[-1]
            fname = hashlib.sha1(data.encode()).hexdigest()[:16] + "." + ext
            (img_dir / fname).write_bytes(base64.b64decode(data))
            out.append({"type": "image_url",
                        "image_url": {"url": f"{rel_prefix}{fname}"}})
        elif t == "image_url":  # 已是 §4.1 形态,原样保留
            out.append(b)
    return out


# ---------- tools / messages 转化 ----------

def conv_tools(tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Anthropic {name,description,input_schema} → OpenAI FC。tools 为 None/缺失 → []。"""
    out: List[Dict[str, Any]] = []
    for t in tools or []:
        f = t.get("function", t)
        out.append({
            "type": "function",
            "function": {
                "name": f.get("name", ""),
                "description": f.get("description", ""),
                "parameters": (f.get("input_schema") or f.get("parameters")
                               or {"type": "object", "properties": {}}),
            },
        })
    return out


def _tool_use_to_call(b: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": b.get("id", ""),
        "type": "function",
        "function": {
            "name": b.get("name", ""),
            "arguments": json.dumps(b.get("input", {}), ensure_ascii=False),
        },
    }


def anthropic_to_openai(rec: Dict[str, Any],
                        img_dir: Path,
                        rel_prefix: str,
                        keep_system: bool = True,
                        prune_tools: bool = False) -> Dict[str, Any]:
    """rec = recorder.py 落盘的中间格式 → §4.1 顶层对象(messages/tools 等)。
    keep_system=False 用于"按 §4.1 把 system 折叠到 user 头部"的场景,但本层只搬运,
    具体折叠策略交给子命令(避免错误改写真实采集)。"""
    tools = conv_tools(rec.get("tools", []))
    messages: List[Dict[str, Any]] = []

    sysv = rec.get("system")
    if sysv and keep_system:
        if isinstance(sysv, list):
            sysv = "\n".join(b.get("text", "") for b in sysv if b.get("type") == "text")
        if isinstance(sysv, str) and sysv.strip():
            messages.append({"role": "system", "content": sysv})

    for m in rec.get("messages", []):
        role = m.get("role")
        blocks = m.get("content")

        if isinstance(blocks, str):
            messages.append({"role": role, "content": blocks})
            continue
        if not isinstance(blocks, list):
            continue

        tool_results = [b for b in blocks if b.get("type") == "tool_result"]
        normal = [b for b in blocks if b.get("type") != "tool_result"]

        if role == "assistant":
            text_parts = [b["text"] for b in normal
                          if b.get("type") == "text" and b.get("text")]
            tool_calls = [_tool_use_to_call(b) for b in normal if b.get("type") == "tool_use"]
            msg: Dict[str, Any] = {"role": "assistant", "content": "\n".join(text_parts)}
            if tool_calls:
                msg["tool_calls"] = tool_calls
                if not text_parts:
                    msg["content"] = ""
            messages.append(msg)

        elif role == "user":
            for tr in tool_results:
                c = tr.get("content")
                if isinstance(c, list):
                    c = "\n".join(x.get("text", "") for x in c if x.get("type") == "text")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get("tool_use_id", ""),
                    "content": c if c is not None else "",
                })
            if normal:
                arr = extract_images(normal, img_dir, rel_prefix)
                if len(arr) == 1 and arr[0]["type"] == "text":
                    messages.append({"role": "user", "content": arr[0]["text"]})
                elif arr:
                    messages.append({"role": "user", "content": arr})

    out_blocks = rec.get("assistant_output", [])
    if out_blocks:
        text_parts = [b["text"] for b in out_blocks
                      if b.get("type") == "text" and b.get("text")]
        tool_calls = [_tool_use_to_call(b) for b in out_blocks if b.get("type") == "tool_use"]
        msg = {"role": "assistant", "content": "\n".join(text_parts)}
        if tool_calls:
            msg["tool_calls"] = tool_calls
            if not text_parts:
                msg["content"] = ""
        messages.append(msg)

    if prune_tools:
        used_names = {
            (c.get("function") or {}).get("name", "")
            for m in messages
            for c in (m.get("tool_calls") or [])
        }
        tools = [
            t for t in tools
            if (t.get("function") or {}).get("name", "") in used_names
        ]

    return {
        "uuid": str(uuid.uuid4()),
        "tools": tools,
        "messages": messages,
        "finish": bool(messages and messages[-1]["role"] == "assistant"),
        "meta": {
            "source": "claude-code-capture",
            "model": rec.get("model"),
            "turns": rec.get("turn_count"),
        },
    }


# ---------- §4.1 schema 校验 ----------

def validate_4_1(obj: Dict[str, Any]) -> List[str]:
    """返回违规说明列表,空 = 通过。"""
    errs: List[str] = []
    if not obj.get("uuid"):
        errs.append("4.1:missing uuid")
    if obj.get("tools") is None:
        errs.append("4.1:tools is null (must be [] when empty)")
    msgs = obj.get("messages")
    if not isinstance(msgs, list) or not msgs:
        errs.append("4.1:messages must be non-empty array")
        return errs

    tool_names = {t.get("function", {}).get("name", "") for t in obj.get("tools", []) or []}
    declared_call_ids: List[str] = []

    for i, m in enumerate(msgs):
        role = m.get("role")
        content = m.get("content")
        if role == "assistant":
            calls = m.get("tool_calls") or []
            if not calls and not (isinstance(content, str) and content.strip()):
                errs.append(f"4.1:msg[{i}] assistant empty (content null/'' and no tool_calls)")
            for c in calls:
                cid = c.get("id", "")
                if not cid:
                    errs.append(f"4.1:msg[{i}] tool_call missing id")
                declared_call_ids.append(cid)
                fn = (c.get("function") or {}).get("name", "")
                if fn and fn not in tool_names:
                    errs.append(f"4.1:msg[{i}] tool_call.name '{fn}' not in tools[]")
                if not isinstance((c.get("function") or {}).get("arguments"), str):
                    errs.append(f"4.1:msg[{i}] tool_call.arguments must be JSON string")
        elif role == "tool":
            tcid = m.get("tool_call_id", "")
            if not tcid:
                errs.append(f"4.1:msg[{i}] tool message missing tool_call_id")
            elif tcid not in declared_call_ids:
                errs.append(f"4.1:msg[{i}] tool_call_id '{tcid}' unpaired")
            if not isinstance(content, str):
                errs.append(f"4.1:msg[{i}] tool content must be string")

    if msgs and msgs[-1].get("role") != "assistant":
        errs.append("4.1:last message must be assistant")
    return errs


# ---------- §4.4 红线 / 反模式 ----------

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def count_tool_rounds(obj: Dict[str, Any]) -> int:
    """一轮 = 一个 assistant.tool_call 与其 role:tool 响应配对。"""
    declared: set[str] = set()
    paired: set[str] = set()
    for m in obj.get("messages", []):
        if m.get("role") == "assistant":
            calls = m.get("tool_calls") or []
            declared.update(c.get("id", "") for c in calls if c.get("id"))
        elif m.get("role") == "tool":
            tcid = m.get("tool_call_id", "")
            if tcid in declared:
                paired.add(tcid)
    return len(paired)


def validate_4_4(obj: Dict[str, Any], *, min_rounds: int = 4,
                 max_rounds: Optional[int] = None) -> List[str]:
    """§4.4 通用硬指标。§5.4 走 (min_rounds=2, max_rounds=6) 例外。"""
    errs: List[str] = []
    r = count_tool_rounds(obj)
    if r < min_rounds:
        errs.append(f"4.4:tool_rounds={r} < {min_rounds}")
    if max_rounds is not None and r > max_rounds:
        errs.append(f"4.4:tool_rounds={r} > {max_rounds}")
    msgs = obj.get("messages") or []
    if msgs and msgs[-1].get("role") != "assistant":
        errs.append("4.4:tail must be assistant")
    return errs


def detect_language(obj: Dict[str, Any]) -> str:
    text = []
    for m in obj.get("messages", []):
        c = m.get("content")
        if isinstance(c, str):
            text.append(c)
        elif isinstance(c, list):
            for b in c:
                if b.get("type") == "text":
                    text.append(b.get("text", ""))
    s = "".join(text)
    if not s:
        return "unknown"
    zh = len(CHINESE_RE.findall(s))
    return "zh" if zh > len(s) * 0.2 else "en"


def tools_used(obj: Dict[str, Any]) -> List[str]:
    seen: List[str] = []
    for m in obj.get("messages", []):
        for c in m.get("tool_calls") or []:
            name = (c.get("function") or {}).get("name", "")
            if name and name not in seen:
                seen.append(name)
    return seen


# ---------- 多样性聚合(跨多条) ----------

def diversity_report(objs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(objs)
    total = len(items)
    if not total:
        return {"total": 0}
    rounds = [count_tool_rounds(o) for o in items]
    langs = Counter(detect_language(o) for o in items)
    combos = Counter("+".join(sorted(tools_used(o))) for o in items)
    is_refl = sum(1 for o in items if (o.get("meta") or {}).get("is_reflection"))

    def bucket(n: int) -> str:
        if n <= 3:
            return "≤3"
        if n <= 6:
            return "4-6"
        if n <= 10:
            return "7-10"
        return "11+"
    rb = Counter(bucket(n) for n in rounds)

    return {
        "total": total,
        "avg_tool_rounds": round(sum(rounds) / total, 2),
        "round_buckets": dict(rb),
        "languages": dict(langs),
        "zh_ratio": round(langs.get("zh", 0) / total, 3),
        "distinct_tool_combos": len(combos),
        "top_tool_combos": combos.most_common(10),
        "reflection_ratio": round(is_refl / total, 3),
    }


# ---------- meta 注入 ----------

def inject_meta(obj: Dict[str, Any], **fields: Any) -> Dict[str, Any]:
    meta = obj.setdefault("meta", {})
    for k, v in fields.items():
        if v is not None:
            meta[k] = v
    if "language" not in meta:
        meta["language"] = detect_language(obj)
    if "tools_used" not in meta:
        meta["tools_used"] = tools_used(obj)
    return obj


# ---------- 工具白名单门禁 ----------

def enforce_tool_whitelist(obj: Dict[str, Any],
                           whitelist: List[str]) -> List[str]:
    """检查 tools[] 与实际调用是否都在白名单内。空白名单 = 不检查。"""
    if not whitelist:
        return []
    errs: List[str] = []
    declared = {t.get("function", {}).get("name", "") for t in obj.get("tools", []) or []}
    extra = declared - set(whitelist)
    if extra:
        errs.append(f"whitelist:tools declares non-whitelisted {sorted(extra)}")
    used = set(tools_used(obj))
    bad = used - set(whitelist)
    if bad:
        errs.append(f"whitelist:used non-whitelisted {sorted(bad)}")
    return errs


# ---------- 子命令通用 CLI ----------

def run_section(section: str,
                strict_extra,            # callable(obj) -> List[str]
                meta_extra,              # callable(obj, rec) -> dict
                indir: str,
                outdir: str,
                imgdir: str,
                max_rounds: Optional[int] = None,
                whitelist: Optional[List[str]] = None,
                prune_tools: bool = True) -> Dict[str, int]:
    """所有 to_section_5_x.py 的公共主体。返回 {accepted, rejected, total}。
    - 校验链: §4.1 → §4.4 → 工具白名单 → 子命令自带 strict_extra
    - 任一失败 → 写 _rejected.jsonl + 错误清单
    - 接受  → 写 <section>.jsonl
    """
    in_p, out_p, img_p = Path(indir), Path(outdir), Path(imgdir)
    out_p.mkdir(parents=True, exist_ok=True)
    img_p.mkdir(parents=True, exist_ok=True)

    accepted = out_p / f"{section}.jsonl"
    rejected = out_p / "_rejected.jsonl"
    reset_file(accepted)
    reset_file(rejected)

    rel_prefix = "../images/"
    a = r = 0
    for f in sorted(in_p.glob("*.json")):
        if f.name.endswith(".gt.json"):
            continue
        rec = load_raw(f)
        obj = anthropic_to_openai(rec, img_p, rel_prefix, prune_tools=prune_tools)
        sidecar = load_sidecar(f)
        obj = inject_meta(obj, **(meta_extra(obj, rec) or {}))
        for key in ("answer_gt", "model_query"):
            if key in sidecar:
                obj[key] = sidecar[key]
        if isinstance(sidecar.get("meta"), dict):
            obj = inject_meta(obj, **sidecar["meta"])

        errs: List[str] = []
        errs += validate_4_1(obj)
        if section == "5_4":
            errs += validate_4_4(obj, min_rounds=2, max_rounds=6)
        else:
            errs += validate_4_4(obj, min_rounds=4, max_rounds=max_rounds)
        if whitelist:
            errs += enforce_tool_whitelist(obj, whitelist)
        errs += (strict_extra(obj) or [])

        if errs:
            r += 1
            dump_jsonl({"source": f.name, "uuid": obj.get("uuid"),
                        "errors": errs}, rejected)
        else:
            a += 1
            dump_jsonl(obj, accepted)

    return {"accepted": a, "rejected": r, "total": a + r}
