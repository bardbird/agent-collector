"""§5.5 多模态 Python FC 强化 — 转化器。

约束(出自需求文档 §5.5):
  · 5.4 所有约束(python 白名单 + 含图 + operations)
  · 必填 answer_gt + model_query
  · 含反思轨迹 5%-10%
  · 调 verifier_5_5.py 做脚本式自检
"""
import argparse, importlib.util, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

WHITELIST = ["python"]
ALLOWED_OPS = {"crop", "rotate", "scale", "filter", "compose",
               "color", "watermark", "perspective", "collage"}


def _load_v():
    p = Path(__file__).resolve().parent.parent / "verifier" / "verifier_5_5.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("verifier_5_5", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_V = _load_v()


def _first_user_has_image(obj):
    for m in obj.get("messages", []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        return isinstance(c, list) and any(b.get("type") == "image_url" for b in c)
    return False


def strict_extra(obj):
    errs = []
    if not _first_user_has_image(obj):
        errs.append("5.5:first user must contain image_url")
    ops = (obj.get("meta") or {}).get("operations") or []
    if not ops:
        errs.append("5.5:meta.operations missing")
    bad = set(ops) - ALLOWED_OPS
    if bad:
        errs.append(f"5.5:operations non-allowed {sorted(bad)}")
    if not obj.get("answer_gt"):
        errs.append("5.5:answer_gt missing")
    if not obj.get("model_query"):
        errs.append("5.5:model_query missing")
    if _V is not None and obj.get("answer_gt"):
        last = next((m for m in reversed(obj["messages"]) if m["role"] == "assistant"), None)
        pred = (last or {}).get("content") or ""
        try:
            res = _V.verify(pred, obj["answer_gt"], obj.get("model_query", ""))
            if not res.get("pass"):
                errs.append(f"5.5:verifier reject: {res.get('reason','')}")
        except Exception as e:
            errs.append(f"5.5:verifier exception: {e}")
    return errs


def meta_extra(obj, rec):
    return {"section": "5.5", "verifier_type": "script",
            "is_reflection": False, "operations": []}


def main():
    ap = argparse.ArgumentParser(description="§5.5 转化器(多模态 Python RL)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_5")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_5", strict_extra, meta_extra,
                               a.indir, a.out, a.images,
                               max_rounds=6, whitelist=WHITELIST)
    print(f"[5.5] {stats}")


if __name__ == "__main__":
    main()
