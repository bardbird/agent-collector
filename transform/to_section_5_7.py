"""§5.7 多模态搜索 RL — 转化器。

约束(出自需求文档 §5.7):
  · 5.6 所有约束(搜索相关工具定义 + tools_used + search_hops)
  · 必填 answer_gt + model_query
  · 多跳搜索 search_hops ≥ 2 (该条层面)
  · 调 verifier_5_7.py
"""
import argparse, importlib.util, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

def _load_v():
    p = Path(__file__).resolve().parent.parent / "verifier" / "verifier_5_7.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("verifier_5_7", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_V = _load_v()


def strict_extra(obj):
    errs = []
    meta = obj.get("meta") or {}
    hops = meta.get("search_hops")
    if not isinstance(hops, int) or hops < 2:
        errs.append("5.7:meta.search_hops must be >=2 (multi-hop required)")
    if not obj.get("tools"):
        errs.append("5.7:tools must contain search-related tool definitions")
    declared = {(t.get("function") or {}).get("name", "") for t in obj.get("tools", [])}
    missing = {"image_search", "web_search", "image_zoom_in"} - declared
    if missing:
        errs.append(f"5.7:tools missing required search definitions {sorted(missing)}")
    used = set(common.tools_used(obj))
    if "web_search" not in used:
        errs.append("5.7:web_search must be used")
    if "image_search" not in used and "image_zoom_in" not in used:
        errs.append("5.7:image_search or image_zoom_in must be used")
    if not obj.get("answer_gt"):
        errs.append("5.7:answer_gt missing")
    if not obj.get("model_query"):
        errs.append("5.7:model_query missing")
    if _V is not None and obj.get("answer_gt"):
        last = next((m for m in reversed(obj["messages"]) if m["role"] == "assistant"), None)
        pred = (last or {}).get("content") or ""
        try:
            res = _V.verify(pred, obj["answer_gt"], obj.get("model_query", ""))
            if not res.get("pass"):
                errs.append(f"5.7:verifier reject: {res.get('reason','')}")
        except Exception as e:
            errs.append(f"5.7:verifier exception: {e}")
    return errs


def meta_extra(obj, rec):
    hops = sum(
        1
        for m in obj.get("messages", [])
        if m.get("role") == "assistant"
        for c in (m.get("tool_calls") or [])
        if (c.get("function") or {}).get("name", "")
    )
    return {"section": "5.7", "search_hops": hops,
            "verifier_type": "script", "domain": "多模态搜索验证"}


def main():
    ap = argparse.ArgumentParser(description="§5.7 转化器(多模态搜索 RL)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_7")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_7", strict_extra, meta_extra,
                               a.indir, a.out, a.images,
                               prune_tools=False)
    print(f"[5.7] {stats}")


if __name__ == "__main__":
    main()
