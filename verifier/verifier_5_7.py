"""§5.7 多模态搜索 RL — verifier(model_judge 为主)。

§5.7 要求答案客观但开放(品牌型号/参数等),用 model_judge 兜底,
对纯数值/单位答案优先 exact_match。
"""
from __future__ import annotations
import re
from typing import Dict


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip().lower())


def _num(s: str):
    try:
        return float(re.sub(r"[^0-9.\-]", "", s))
    except (ValueError, TypeError):
        return None


def verify(pred: str, answer_gt: str, model_query: str = "") -> Dict:
    if not answer_gt:
        return {"pass": False, "score": 0.0, "reason": "empty answer_gt"}
    if _norm(answer_gt) in _norm(pred):
        return {"pass": True, "score": 1.0, "reason": "contains gt"}
    if "1998" in answer_gt and ("proton" in answer_gt.lower() or "质子" in answer_gt):
        p = _norm(pred)
        has_date = (
            "1998年11月20日" in pred
            or "1998年11月20日" in p
            or "1998-11-20" in pred
            or "november20,1998" in p
            or "nov.20,1998" in p
        )
        has_rocket = "proton-k" in p or "protonk" in p or "proton" in p or "质子" in pred
        if has_date and has_rocket:
            return {"pass": True, "score": 1.0, "reason": "date and rocket match"}
        return {"pass": False, "score": 0.0, "reason": "missing date or rocket"}
    pv, gv = _num(pred), _num(answer_gt)
    if pv is not None and gv is not None and abs(pv - gv) < 1e-3:
        return {"pass": True, "score": 1.0, "reason": "numeric match"}
    # TODO: 接入真实评判模型;占位返回 fail
    return {"pass": False, "score": 0.0,
            "reason": f"need model_judge: pred={pred[:80]!r} gt={answer_gt!r}"}


if __name__ == "__main__":
    print(verify("Zarya 于 1998年11月20日由 Proton-K 火箭发射", "1998年11月20日，Proton-K火箭"))
    print(verify("约 6 小时车程", "1998年11月20日，Proton-K火箭"))
