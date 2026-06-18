"""§5.4 多模态多轮 Python 轨迹 — 转化器。

约束(出自需求文档 §5.4):
  · 工具白名单: {python}
  · user 首条 content 必须为 array 且含 image_url
  · 轮次例外: 2 ≤ turns ≤ 6 (其余分项是 ≥ 4)
  · meta.operations ⊆ {crop,rotate,scale,filter,compose,color,watermark,perspective,collage}
  · 反思轨迹占比 ≈ 5%(批次级)
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

WHITELIST = ["python"]
ALLOWED_OPS = {"crop", "rotate", "scale", "filter", "compose",
               "color", "watermark", "perspective", "collage"}


def _first_user_has_image(obj):
    for m in obj.get("messages", []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, list):
            return any(b.get("type") == "image_url" for b in c)
        return False
    return False


def strict_extra(obj):
    errs = []
    if not _first_user_has_image(obj):
        errs.append("5.4:first user message must contain image_url")
    ops = (obj.get("meta") or {}).get("operations") or []
    if not ops:
        errs.append("5.4:meta.operations missing")
    bad = set(ops) - ALLOWED_OPS
    if bad:
        errs.append(f"5.4:meta.operations has non-allowed {sorted(bad)}")
    return errs


def meta_extra(obj, rec):
    return {"section": "5.4", "is_reflection": False, "operations": []}


def main():
    ap = argparse.ArgumentParser(description="§5.4 转化器(多模态 Python SFT)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_4")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_4", strict_extra, meta_extra,
                               a.indir, a.out, a.images,
                               max_rounds=6, whitelist=WHITELIST)
    print(f"[5.4] {stats}")


if __name__ == "__main__":
    main()
