"""§5.2 Skills RL 轨迹数据 — 转化器。

约束(出自需求文档 §5.2):
  · 5.1 所有约束(工具白名单 + system-reminder + skill_name)
  · 必填 answer_gt + model_query
  · ≥ 4 轮; 反思轨迹占比 5%-10%(批次级别,本脚本只标记单条)
  · 调 verifier/verifier_5_2.py:verify() 自检
"""
import argparse, importlib.util, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WHITELIST = ["Skill", "AskUserQuestion"]


def _load_verifier():
    p = Path(__file__).resolve().parent.parent / "verifier" / "verifier_5_2.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location("verifier_5_2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_V = _load_verifier()


def _has_sr(obj):
    for m in obj.get("messages", []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str) and "<system-reminder>" in c:
            return True
        if isinstance(c, list):
            for b in c:
                if b.get("type") == "text" and "<system-reminder>" in b.get("text", ""):
                    return True
    return False


def strict_extra(obj):
    errs = []
    if not _has_sr(obj):
        errs.append("5.2:no <system-reminder> in user message")
    if not (obj.get("meta") or {}).get("skill_name"):
        errs.append("5.2:meta.skill_name missing")
    if not obj.get("answer_gt"):
        errs.append("5.2:answer_gt missing")
    if not obj.get("model_query"):
        errs.append("5.2:model_query missing")
    if _V is not None and obj.get("answer_gt"):
        # 末条 assistant 文本 = pred
        last = next((m for m in reversed(obj["messages"]) if m["role"] == "assistant"), None)
        pred = (last or {}).get("content") or ""
        try:
            res = _V.verify(pred, obj["answer_gt"], obj.get("model_query", ""))
            if not res.get("pass"):
                errs.append(f"5.2:verifier reject: {res.get('reason','')}")
        except Exception as e:
            errs.append(f"5.2:verifier exception: {e}")
    return errs


def meta_extra(obj, rec):
    out = {"section": "5.2", "verifier_type": "model_judge"}
    for m in obj.get("messages", []):
        for c in m.get("tool_calls") or []:
            if (c.get("function") or {}).get("name") == "Skill":
                try:
                    args = json.loads(c["function"]["arguments"])
                    if args.get("skill"):
                        out["skill_name"] = args["skill"]
                except Exception:
                    pass
    return out


def main():
    ap = argparse.ArgumentParser(description="§5.2 转化器(RL)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_2")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_2", strict_extra, meta_extra,
                               a.indir, a.out, a.images, whitelist=WHITELIST)
    print(f"[5.2] {stats}")


if __name__ == "__main__":
    main()
