"""§5.3 RL 高质量 QA(沙盒) — verifier。

§5.3 强调"结果可验证、0/1 二值判定",首选 exact_match。
"""
from __future__ import annotations
import re
from typing import Dict


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip().lower())


def verify(pred: str, answer_gt: str, model_query: str = "") -> Dict:
    if not answer_gt:
        return {"pass": False, "score": 0.0, "reason": "empty answer_gt"}
    pn, gn = _norm(pred), _norm(answer_gt)
    if pn == gn or gn in pn:
        return {"pass": True, "score": 1.0, "reason": "match"}
    # 数值容忍 (±1e-6 或相对 0.1%)
    try:
        pv = float(re.sub(r"[^0-9.\-]", "", pred))
        gv = float(re.sub(r"[^0-9.\-]", "", answer_gt))
        if abs(pv - gv) < 1e-6 or (gv and abs(pv - gv) / abs(gv) < 1e-3):
            return {"pass": True, "score": 1.0, "reason": "numeric match"}
    except (ValueError, TypeError):
        pass
    return {"pass": False, "score": 0.0,
            "reason": f"mismatch: pred={pred[:80]!r} gt={answer_gt[:80]!r}"}


if __name__ == "__main__":
    print(verify("1284350.75 元", "1284350.75"))
    print(verify("总销售额 1,284,350.75", "1284350.75"))
