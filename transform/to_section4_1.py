"""
to_section4_1.py — Anthropic 原始中间格式 → §4.1 客户 messages 格式（JSONL）

把 recorder.py 落盘的 out/raw_turns/*.json 转成 §4.1 OpenAI function calling 格式。

用法：
  python transform/to_section4_1.py
  python transform/to_section4_1.py --in out/raw_turns --out out/jsonl --images out/images

转换规则（对照 §4.1 / §9 附录 A）：
  · tools:  {name,description,input_schema} → {type:function,function:{name,description,parameters}}
  · assistant tool_use → tool_calls[].arguments（JSON 序列化为【字符串】）
  · tool_result（Anthropic 放在 user message 的 content block）→ 独立 role:tool 消息
  · 图片 base64 → 落盘成相对路径文件 + {type:image_url, image_url:{url}}
  · 补 uuid / finish / meta 基本字段

已知边界（本样例阶段不处理，需后续/人工）：
  · system-reminder 注入位置：Claude Code 的 CLAUDE.md/skills 多注入在 system，
    §4.1 红线要求注入在 user content 头部 —— 这里原样保留 system 并在 meta.capture_note 标注。
  · 不构造反思轨迹（meta.is_reflection 恒 false，按本阶段约定）。
  · thinking blocks 默认丢弃（要不要保留待甲方明确）。
  · meta.domain/language 等留默认，需后续按内容打标。
"""
import json
import base64
import hashlib
import argparse
import uuid
from pathlib import Path


def conv_tools(tools):
    out = []
    for t in tools or []:
        f = t.get("function", t)  # 兼容 Anthropic / OpenAI 两种输入
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


def _tool_use_to_call(b):
    return {
        "id": b.get("id", ""),
        "type": "function",
        "function": {
            "name": b.get("name", ""),
            "arguments": json.dumps(b.get("input", {}), ensure_ascii=False),
        },
    }


def _user_normal_blocks(blocks, img_dir, rel_prefix):
    """user message 中非 tool_result 的 blocks → §4.1 user content(array)。"""
    arr = []
    for b in blocks:
        t = b.get("type")
        if t == "text":
            arr.append({"type": "text", "text": b.get("text", "")})
        elif t == "image":
            src = b.get("source", {})
            data = src.get("data")
            if data:  # base64 → 落盘
                ext = (src.get("media_type") or "image/png").split("/")[-1]
                fname = hashlib.sha1(data.encode()).hexdigest()[:16] + "." + ext
                (img_dir / fname).write_bytes(base64.b64decode(data))
                arr.append({"type": "image_url", "image_url": {"url": f"{rel_prefix}{fname}"}})
    return arr


def transform(rec, img_dir, rel_prefix):
    tools = conv_tools(rec.get("tools", []))
    messages = []
    has_system = False

    # system（原样保留；位置边界见模块注释）
    sysv = rec.get("system")
    if sysv:
        if isinstance(sysv, list):
            sysv = "\n".join(b.get("text", "") for b in sysv if b.get("type") == "text")
        if sysv.strip():
            messages.append({"role": "system", "content": sysv})
            has_system = True

    # 历史 messages（Anthropic 累积格式）
    for m in rec.get("messages", []):
        role = m.get("role")
        blocks = m.get("content")

        if isinstance(blocks, str):  # 纯文本
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
            msg = {"role": "assistant", "content": "\n".join(text_parts)}
            if tool_calls:
                msg["tool_calls"] = tool_calls
                if not text_parts:
                    msg["content"] = ""  # 有 tool_calls 时可为空
            messages.append(msg)

        elif role == "user":
            # tool_result → 独立 role:tool 消息（Anthropic→OpenAI 关键转换）
            for tr in tool_results:
                c = tr.get("content")
                if isinstance(c, list):  # tool_result.content 可能是 block list
                    c = "\n".join(x.get("text", "") for x in c if x.get("type") == "text")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get("tool_use_id", ""),
                    "content": c if c is not None else "",
                })
            if normal:
                arr = _user_normal_blocks(normal, img_dir, rel_prefix)
                if len(arr) == 1 and arr[0]["type"] == "text":
                    messages.append({"role": "user", "content": arr[0]["text"]})
                elif arr:
                    messages.append({"role": "user", "content": arr})

    # 追加最终轮 assistant 输出（recorder 单独捕获）
    out_blocks = rec.get("assistant_output", [])
    if out_blocks:
        text_parts = [b["text"] for b in out_blocks
                      if b.get("type") == "text" and b.get("text")]
        tool_calls = [_tool_use_to_call(b) for b in out_blocks if b.get("type") == "tool_use"]
        msg = {"role": "assistant", "content": "\n".join(text_parts)}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        messages.append(msg)

    finish = bool(messages and messages[-1]["role"] == "assistant")

    return {
        "uuid": str(uuid.uuid4()),
        "tools": tools,
        "messages": messages,
        "finish": finish,
        "meta": {
            "source": "claude-code-capture",
            "model": rec.get("model"),
            "is_reflection": False,            # 本阶段不构造反思
            "language": "zh",                  # 后续按实际检测
            "turns": rec.get("turn_count"),
            "capture_note": "system-reminder 位置需按 §4.1 校正" if has_system else "",
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()

    indir, outdir, imgdir = Path(a.indir), Path(a.out), Path(a.images)
    outdir.mkdir(parents=True, exist_ok=True)
    imgdir.mkdir(parents=True, exist_ok=True)
    rel_prefix = "../images/"   # jsonl 在 out/jsonl/，图片在 out/images/

    n = 0
    for f in sorted(indir.glob("*.json")):
        rec = json.loads(f.read_text())
        obj = transform(rec, imgdir, rel_prefix)
        (outdir / (f.stem + ".jsonl")).write_text(
            json.dumps(obj, ensure_ascii=False) + "\n"
        )
        n += 1
    print(f"[transform] {n} task(s) -> {outdir}/  (images -> {imgdir}/)")


if __name__ == "__main__":
    main()
