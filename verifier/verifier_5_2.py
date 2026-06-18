"""§5.2 Skills RL — verifier。

接口签名固定为 verify(pred, answer_gt, model_query) -> {pass, score, reason}。
本骨架按 §C.1 实现 3 种 verifier_type 的 dispatch:
  · exact_match : 数值/日期等精确匹配(规范化后)
  · model_judge : 调外部评判模型(本骨架仅做关键词匹配占位,真接入留 TODO)
  · script      : 子项不适用(交给 5_3/5_5)

§5.2 默认 verifier_type=model_judge(周报等开放式)。
"""
from __future__ import annotations
import re
from typing import Dict


def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[,，、\s]+", " ", s)
    return s


def _exact_match(pred: str, gt: str) -> Dict:
    if _normalize(pred) == _normalize(gt):
        return {"pass": True, "score": 1.0, "reason": "exact match"}
    # 数值容忍
    try:
        if abs(float(re.sub(r"[^0-9.\-]", "", pred)) -
               float(re.sub(r"[^0-9.\-]", "", gt))) < 1e-6:
            return {"pass": True, "score": 1.0, "reason": "numeric match"}
    except (ValueError, TypeError):
        pass
    return {"pass": False, "score": 0.0,
            "reason": f"mismatch: pred={pred[:80]!r} gt={gt[:80]!r}"}


def _model_judge(pred: str, gt: str, query: str) -> Dict:
    # TODO: 接入真实评判模型(本骨架按"pred 必须包含 gt 关键词"占位,
    # 真实交付前需替换为 LLM 评判调用)
    if not gt:
        return {"pass": False, "score": 0.0, "reason": "empty gt"}
    hit = _normalize(gt) in _normalize(pred) or any(
        kw in pred for kw in re.split(r"[\s，、,]+", gt) if len(kw) >= 2)
    return {"pass": hit, "score": 1.0 if hit else 0.0,
            "reason": "keyword hit (placeholder for model_judge)"}


def verify(pred: str, answer_gt: str, model_query: str = "",
           verifier_type: str = "model_judge") -> Dict:
    if verifier_type == "exact_match":
        return _exact_match(pred, answer_gt)
    if verifier_type == "model_judge":
        return _model_judge(pred, answer_gt, model_query)
    return {"pass": False, "score": 0.0,
            "reason": f"unsupported verifier_type={verifier_type}"}


if __name__ == "__main__":
    print(verify("数据清洗完成率 100%", "数据清洗", verifier_type="model_judge"))
    print(verify("answer is 42", "42", verifier_type="exact_match"))
