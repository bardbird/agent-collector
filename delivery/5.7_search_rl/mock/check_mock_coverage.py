"""mock/check_mock_coverage.py — §C.2 一致性校验。

遍历 out/jsonl/**/*.jsonl 中所有 assistant.tool_calls,
按 sha256(tool_name + json.dumps(arguments, sort_keys=True)) 检查
是否每条都在 mock/mock_responses.jsonl 中有命中。

未覆盖项落 mock/_missing_mocks.jsonl,便于补录。

§5.6/§5.7/§5.8/§5.9 类数据交付前必跑。
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

# §5.6/5.7/5.8/5.9 需要 mock 的工具集;不在此集合的(如 5.1 的 Skill / 5.4 的 python)跳过
NEED_MOCK = {
    "image_search", "web_search", "image_zoom_in",  # 5.6/5.7
    # 5.8/5.9 工具集合是开放的,由 mock_responses.jsonl 自身定义白名单
}


def req_hash(tool: str, args: dict) -> str:
    raw = tool + json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_known(path: Path):
    keys = set()
    tools = set()
    if not path.exists():
        return keys, tools
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        rec = json.loads(ln)
        t = rec.get("tool_name", "")
        a = rec.get("request", {})
        keys.add(rec.get("request_hash") or req_hash(t, a))
        tools.add(t)
    return keys, tools


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl-root", default="out/jsonl")
    ap.add_argument("--db", default="mock/mock_responses.jsonl")
    ap.add_argument("--missing", default="mock/_missing_mocks.jsonl")
    a = ap.parse_args()

    db_keys, db_tools = load_known(Path(a.db))
    need = NEED_MOCK | db_tools  # 已固化的 tools 必须 100% 命中

    missing = []
    total = hit = skipped = 0
    for f in Path(a.jsonl_root).rglob("*.jsonl"):
        if f.name.startswith("_"):
            continue
        for ln in f.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            obj = json.loads(ln)
            for m in obj.get("messages", []):
                if m.get("role") != "assistant":
                    continue
                for c in m.get("tool_calls") or []:
                    tool = (c.get("function") or {}).get("name", "")
                    if tool not in need:
                        skipped += 1
                        continue
                    try:
                        args = json.loads(c["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    k = req_hash(tool, args)
                    total += 1
                    if k in db_keys:
                        hit += 1
                    else:
                        missing.append({"file": str(f), "uuid": obj.get("uuid"),
                                        "tool_name": tool, "arguments": args,
                                        "request_hash": k})

    Path(a.missing).parent.mkdir(parents=True, exist_ok=True)
    with open(a.missing, "w", encoding="utf-8") as g:
        for r in missing:
            g.write(json.dumps(r, ensure_ascii=False) + "\n")

    rate = (hit / total * 100) if total else 100.0
    print(f"[coverage] total={total} hit={hit} miss={len(missing)} "
          f"skipped(no-mock-needed)={skipped} rate={rate:.1f}% "
          f"→ {a.missing}")


if __name__ == "__main__":
    main()
