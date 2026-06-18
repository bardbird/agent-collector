"""§5.9 工具调用泛化 RL — verifier。

§5.9 强调"任务是否完成、调用是否高效、参数是否正确、是否合适时机停止"。
最终结果维度走 exact_match;过程维度(高效/参数正确)由 dispatch 给出 partial score。
"""
from __future__ import annotations
import re
from typing import Dict


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip().lower())


def verify(pred: str, answer_gt: str, model_query: str = "") -> Dict:
    if not answer_gt:
        return {"pass": False, "score": 0.0, "reason": "empty answer_gt"}
    if _norm(answer_gt) in _norm(pred):
        return {"pass": True, "score": 1.0, "reason": "contains gt"}
    if answer_gt and re.search(r"(?<!\d)" + re.escape(answer_gt[:-3]) + r",?" + re.escape(answer_gt[-3:]) + r"(?!\d)", pred or ""):
        return {"pass": True, "score": 1.0, "reason": "contains numeric gt with thousands separator"}
    try:
        pv = float(re.sub(r"[^0-9.\-]", "", pred))
        gv = float(re.sub(r"[^0-9.\-]", "", answer_gt))
        if abs(pv - gv) < 1e-3:
            return {"pass": True, "score": 1.0, "reason": "numeric match"}
    except (ValueError, TypeError):
        pass
    return {"pass": False, "score": 0.0,
            "reason": f"final answer mismatch: pred={pred[:80]!r} gt={answer_gt!r}"}


if __name__ == "__main__":
    print(verify("The cheapest AirPods Pro 3 is on PDD at ¥1,599.", "1599"))
