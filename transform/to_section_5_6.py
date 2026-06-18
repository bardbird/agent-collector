"""§5.6 多模态搜索 SFT — 转化器。

约束(出自需求文档 §5.6):
  · tools 必须包含 image_search / web_search / image_zoom_in 等搜索相关工具定义
  · meta.search_hops ≥ 1, meta.tools_used 必填
  · mock 覆盖率交给 mock/check_mock_coverage.py 单独跑
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SEARCH_TOOLS = {"image_search", "web_search", "image_zoom_in"}
REQUIRED_NAMES = {"image_search", "web_search", "image_zoom_in"}
ANSWER_SIGNALS = (
    ("意图", "搜索目的", "要解决的问题"),
    ("改写", "检索词", "query"),
    ("证据", "来源", "引用", "url"),
    ("最终", "答案", "caption", "结论", "完整", "科普说明", "可引用"),
)


def strict_extra(obj):
    errs = []
    meta = obj.get("meta") or {}
    hops = meta.get("search_hops")
    if not isinstance(hops, int) or hops < 1:
        errs.append("5.6:meta.search_hops must be int >= 1")
    if not meta.get("tools_used"):
        errs.append("5.6:meta.tools_used missing")
    if not obj.get("tools"):
        errs.append("5.6:tools must contain search-related tool definitions")
    declared = {(t.get("function") or {}).get("name", "") for t in obj.get("tools", [])}
    missing_declared = REQUIRED_NAMES - declared
    if missing_declared:
        errs.append(f"5.6:tools missing required search definitions {sorted(missing_declared)}")
    used = set(common.tools_used(obj))
    if not any(name in SEARCH_TOOLS for name in used):
        errs.append("5.6:no actual search tool call")
    if "web_search" not in used:
        errs.append("5.6:web_search must be used")
    if "image_search" not in used and "image_zoom_in" not in used:
        errs.append("5.6:image_search or image_zoom_in must be used for multimodal input")
    user_has_image = any(
        m.get("role") == "user"
        and isinstance(m.get("content"), list)
        and any(b.get("type") == "image_url" for b in m.get("content", []))
        for m in obj.get("messages", [])
    )
    if not user_has_image:
        errs.append("5.6:user content must include image_url")
    final = ""
    for m in reversed(obj.get("messages", [])):
        if m.get("role") == "assistant" and not m.get("tool_calls"):
            final = m.get("content") or ""
            break
    lower = final.lower()
    for group in ANSWER_SIGNALS:
        if not any(sig.lower() in lower for sig in group):
            errs.append(f"5.6:final answer missing signal {group[0]}")
    if "mock://" not in final and "http" not in final and "来源" not in final:
        errs.append("5.6:final answer missing evidence citation")
    return errs


def meta_extra(obj, rec):
    hops = sum(
        1
        for m in obj.get("messages", [])
        if m.get("role") == "assistant"
        for c in (m.get("tool_calls") or [])
        if (c.get("function") or {}).get("name", "") in SEARCH_TOOLS
    )
    return {"section": "5.6", "search_hops": hops, "domain": "图文/页面/文档检索问答"}


def main():
    ap = argparse.ArgumentParser(description="§5.6 转化器(多模态搜索 SFT)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_6")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_6", strict_extra, meta_extra,
                               a.indir, a.out, a.images,
                               prune_tools=False)
    print(f"[5.6] {stats}")


if __name__ == "__main__":
    main()
