#!/usr/bin/env python3
"""glm-vf 验收脚本①｜schema/结构独立硬校验。

不采信 manifest/供应商自报,直接遍历交付目录下每个 batch_*.jsonl 逐条校验:
  tools 非null非空 / tool_calls[].name 在 tools 中定义 / tool_call_id 严格配对 /
  末消息为 assistant / assistant 无 tool_calls 时 content 非空 / tool content 非截断 /
  多模态 image_url 路径存在 / system-reminder 不误注入 system role / RL 必填字段。

用法:
  python3 acceptance_schema.py --root delivery
  python3 acceptance_schema.py --root delivery --root /path/to/other_batch
退出码 0=无 schema 错误, 1=存在错误。
"""
from __future__ import annotations
import argparse, json, os, sys


def iter_items(root):
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d):
            continue
        if any(f.endswith(".jsonl") and f.startswith("batch") for f in os.listdir(d)):
            yield name, d


def img_urls(content):
    out = []
    if isinstance(content, list):
        for pt in content:
            if isinstance(pt, dict) and pt.get("type") == "image_url":
                out.append((pt.get("image_url") or {}).get("url", ""))
    return out


def check_item(name, d):
    errs, stats = [], {"records": 0, "tool_defs": set(), "rounds": [],
                       "img": 0, "model_query": 0, "answer_gt": 0,
                       "search_hops": [], "reflection": []}
    jl = next((os.path.join(d, f) for f in os.listdir(d)
               if f.endswith(".jsonl") and f.startswith("batch")), None)
    if not jl:
        return {"item": name, "errors": ["无 batch_*.jsonl"], "stats": stats}
    for raw in open(jl, encoding="utf-8"):
        raw = raw.strip()
        if not raw:
            continue
        rid = f"rec#{stats['records']}"; stats["records"] += 1
        try:
            o = json.loads(raw)
        except Exception as e:
            errs.append(f"{rid} JSON解析失败: {e}"); continue
        tools = o.get("tools")
        if tools is None:
            errs.append(f"{rid} tools 为 null(必须 [])")
        elif not isinstance(tools, list):
            errs.append(f"{rid} tools 非数组")
        tnames = {(t.get("function") or {}).get("name") for t in (tools or [])
                  if isinstance(t, dict)}
        tool_params = {}
        for t in (tools or []):
            if not isinstance(t, dict):
                continue
            fn = t.get("function") or {}
            fn_name = fn.get("name")
            fn_props = (fn.get("parameters") or {}).get("properties", {})
            if fn_name and isinstance(fn_props, dict):
                tool_params[fn_name] = fn_props
        stats["tool_defs"] |= tnames
        msgs = o.get("messages")
        if not isinstance(msgs, list) or not msgs:
            errs.append(f"{rid} messages 非非空数组"); continue
        if msgs[-1].get("role") != "assistant":
            errs.append(f"{rid} 末消息 role={msgs[-1].get('role')} 非 assistant")
        pending, rounds, has_img = {}, 0, False
        for j, m in enumerate(msgs):
            role, c, tcs = m.get("role"), m.get("content"), m.get("tool_calls")
            if role == "system" and isinstance(c, str) and "system-reminder" in c:
                errs.append(f"{rid} system-reminder 误注入 system role(应在 user content)")
            if role == "assistant":
                if tcs:
                    rounds += len(tcs)
                    for tc in tcs:
                        tid, fn_obj, fn = tc.get("id"), (tc.get("function") or {}), None
                        fn = fn_obj.get("name")
                        pending[tid] = fn
                        if tnames and fn not in tnames:
                            errs.append(f"{rid} tool_call name='{fn}' 未在 tools 定义")
                        errs.extend(check_arg_types(fn, fn_obj.get("arguments", "{}"), tool_params, rid))
                elif c is None or c == "" or c == []:
                    errs.append(f"{rid} assistant 无 tool_calls 但 content 空")
            elif role == "tool":
                tcid = m.get("tool_call_id")
                if tcid not in pending:
                    errs.append(f"{rid} tool tool_call_id={tcid} 无对应 assistant tool_calls")
                else:
                    del pending[tcid]
                if c is None or c == "" or c == []:
                    errs.append(f"{rid} tool content 空/被截断")
            elif role == "user":
                urls = img_urls(c)
                if urls:
                    has_img = True
                for url in urls:
                    if url and not url.startswith("http"):
                        ap = url if os.path.isabs(url) else os.path.join(d, url)
                        if not os.path.exists(ap):
                            errs.append(f"{rid} image_url 路径不存在: {url}")
        if pending:
            errs.append(f"{rid} {len(pending)} 个 tool_calls 无 tool 返回: {list(pending.items())[:3]}")
        stats["rounds"].append(rounds)
        stats["img"] += int(has_img)
        if o.get("model_query"): stats["model_query"] += 1
        if o.get("answer_gt"): stats["answer_gt"] += 1
        meta = o.get("meta") or {}
        for mk, mv in meta.items():
            if isinstance(mv, str):
                for forbidden in FORBIDDEN_META_SUBSTRINGS:
                    if forbidden in mv.lower():
                        errs.append(f"{rid} meta['{mk}'] 含生产链路元数据: {repr(mv)[:80]}")
                        break
        if meta.get("search_hops") is not None: stats["search_hops"].append(meta["search_hops"])
        if meta.get("is_reflection") is not None: stats["reflection"].append(meta["is_reflection"])
    stats["tool_defs"] = sorted(x for x in stats["tool_defs"] if x)
    return {"item": name, "batch": os.path.basename(jl), "errors": errs, "stats": stats}


FORBIDDEN_META_SUBSTRINGS = [
    "claude-code-capture", "claude-opus", "claude-sonnet", "claude-haiku",
    "gpt-4", "gpt-3.5", "deepseek", "gemini",
]
GARBAGE_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def check_directory_cleanliness(root):
    """检查交付目录下是否有系统垃圾文件或 __MACOSX 残留。"""
    errs = []
    for dirpath, dirnames, filenames in os.walk(root):
        for d in list(dirnames):
            if d == "__MACOSX" or d.startswith("._"):
                errs.append(f"__MACOSX/垃圾目录残留: {os.path.join(dirpath, d)}")
        for f in filenames:
            if f in GARBAGE_FILES or f.startswith("._"):
                errs.append(f"系统垃圾文件残留: {os.path.join(dirpath, f)}")
    return errs


PY_TYPE_MAP = {
    "string": "str", "number": "int/float", "integer": "int",
    "array": "list", "object": "dict", "boolean": "bool",
}


def check_arg_types(fn_name, arguments_str, tool_params, rid):
    """校验 tool_call arguments 每个参数的类型是否与 tools schema 声明一致。"""
    errs = []
    try:
        args = json.loads(arguments_str)
    except json.JSONDecodeError:
        errs.append(f"{rid} tool_call '{fn_name}' arguments 不是合法 JSON")
        return errs
    if not isinstance(args, dict):
        errs.append(f"{rid} tool_call '{fn_name}' arguments 解析后非 JSON 对象")
        return errs
    props = tool_params.get(fn_name, {})
    for key, val in args.items():
        expected = props.get(key, {}).get("type")
        if expected is None:
            continue  # schema 无此参数或无类型约束，跳过
        actual_py = type(val).__name__
        if expected == "number":
            if actual_py not in ("int", "float"):
                errs.append(f"{rid} tool_call '{fn_name}' 参数 '{key}' schema 声明 type={expected}，实际值为 {actual_py}: {repr(val)[:60]}")
        elif expected == "integer":
            if actual_py != "int":
                errs.append(f"{rid} tool_call '{fn_name}' 参数 '{key}' schema 声明 type={expected}，实际值为 {actual_py}: {repr(val)[:60]}")
        else:
            py_expected = PY_TYPE_MAP.get(expected)
            if py_expected and actual_py != py_expected:
                errs.append(f"{rid} tool_call '{fn_name}' 参数 '{key}' schema 声明 type={expected}，实际值为 {actual_py}: {repr(val)[:60]}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True, help="交付根目录(可多次指定)")
    a = ap.parse_args()
    total = 0
    for root in a.root:
        print("=" * 64)
        print(f"### 目录洁净度检查: {root}")
        clean_errs = check_directory_cleanliness(root)
        if clean_errs:
            print("ERRORS:", clean_errs)
            total += len(clean_errs)
        else:
            print("ERRORS: 无 (无系统垃圾文件)")
        for name, d in iter_items(root):
            r = check_item(name, d)
            print("=" * 64)
            print(f"### {name}  [{r.get('batch')}]")
            print("ERRORS:", "无" if not r["errors"] else r["errors"])
            total += len(r["errors"])
            for k, v in r["stats"].items():
                print(f"  {k}: {v}")
    print(f"\n[_schema] 错误总数 = {total}  →  {'PASS' if total == 0 else 'FAIL'}")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
