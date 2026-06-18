"""§5.3 RL 高质量 QA 数据集(沙盒验证) — 转化器。

约束(出自需求文档 §5.3):
  · 工具白名单: {Skill, Bash}(沙盒执行)
  · 必填 answer_gt + model_query
  · meta.sandbox=true, meta.verifier_type ∈ {exact_match, model_judge, script}
  · answer_gt 必须唯一且明确(0/1 二值判定)
"""
import argparse, importlib.util, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

WHITELIST = ["Skill", "Bash"]
ALLOWED_VTYPE = {"exact_match", "model_judge", "script"}


def _load_v():
    p = Path(__file__).resolve().parent.parent / "verifier" / "verifier_5_3.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("verifier_5_3", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_V = _load_v()


def strict_extra(obj):
    errs = []
    meta = obj.get("meta") or {}
    if not meta.get("sandbox"):
        errs.append("5.3:meta.sandbox must be true")
    if meta.get("verifier_type") not in ALLOWED_VTYPE:
        errs.append(f"5.3:meta.verifier_type must be one of {ALLOWED_VTYPE}")
    if not obj.get("answer_gt"):
        errs.append("5.3:answer_gt missing")
    if not obj.get("model_query"):
        errs.append("5.3:model_query missing")
    if _V is not None and obj.get("answer_gt"):
        last = next((m for m in reversed(obj["messages"]) if m["role"] == "assistant"), None)
        pred = (last or {}).get("content") or ""
        try:
            res = _V.verify(pred, obj["answer_gt"], obj.get("model_query", ""))
            if not res.get("pass"):
                errs.append(f"5.3:verifier reject: {res.get('reason','')}")
        except Exception as e:
            errs.append(f"5.3:verifier exception: {e}")
    return errs


def meta_extra(obj, rec):
    return {"section": "5.3", "sandbox": True, "verifier_type": "exact_match"}


def main():
    ap = argparse.ArgumentParser(description="§5.3 转化器(RL QA)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_3")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_3", strict_extra, meta_extra,
                               a.indir, a.out, a.images, whitelist=WHITELIST)
    print(f"[5.3] {stats}")


if __name__ == "__main__":
    main()
