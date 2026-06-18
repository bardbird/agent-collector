"""§5.9 工具调用泛化 RL — 转化器。

约束(出自需求文档 §5.9):
  · 5.8 所有约束(scene + tools_used)
  · 必填 answer_gt + model_query
  · meta.situation ∈ {normal_chain, error_recovery, redundant_call,
                      param_fix, tool_fail, early_stop}
  · 调 verifier_5_9.py
"""
import argparse, importlib.util, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ALLOWED_SCENES = {
    "search", "map_local", "ecommerce", "calendar_email",
    "weather_travel", "table_data", "code_devops",
    "knowledge_qa", "device_control", "mixed",
}
ALLOWED_SITS = {"normal_chain", "error_recovery", "redundant_call",
                "param_fix", "tool_fail", "early_stop"}


def _load_v():
    p = Path(__file__).resolve().parent.parent / "verifier" / "verifier_5_9.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("verifier_5_9", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_V = _load_v()


def strict_extra(obj):
    errs = []
    meta = obj.get("meta") or {}
    if meta.get("scene") not in ALLOWED_SCENES:
        errs.append(f"5.9:meta.scene must be in {sorted(ALLOWED_SCENES)}")
    if meta.get("situation") not in ALLOWED_SITS:
        errs.append(f"5.9:meta.situation must be in {sorted(ALLOWED_SITS)}")
    if not obj.get("answer_gt"):
        errs.append("5.9:answer_gt missing")
    if not obj.get("model_query"):
        errs.append("5.9:model_query missing")
    if _V is not None and obj.get("answer_gt"):
        last = next((m for m in reversed(obj["messages"]) if m["role"] == "assistant"), None)
        pred = (last or {}).get("content") or ""
        try:
            res = _V.verify(pred, obj["answer_gt"], obj.get("model_query", ""))
            if not res.get("pass"):
                errs.append(f"5.9:verifier reject: {res.get('reason','')}")
        except Exception as e:
            errs.append(f"5.9:verifier exception: {e}")
    return errs


def meta_extra(obj, rec):
    return {"section": "5.9", "scene": "mixed",
            "situation": "normal_chain", "verifier_type": "exact_match"}


def main():
    ap = argparse.ArgumentParser(description="§5.9 转化器(工具泛化 RL)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_9")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_9", strict_extra, meta_extra,
                               a.indir, a.out, a.images)
    print(f"[5.9] {stats}")


if __name__ == "__main__":
    main()
