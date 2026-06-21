"""§5.7 multimodal search RL verifier.

answer_gt can be a JSON object/list or a delimiter-separated fact list. Every
non-empty fact from answer_gt must be present in pred after light normalization.
This keeps the verifier usable for full batches beyond the Zarya POC sample.
"""
from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List


def _norm(s: str) -> str:
    return re.sub(r"[\s,，、。；;：:（）()\\[\\]【】\"'`*_\\-]+", "", (s or "").strip().lower())


def _date_variants(s: str) -> List[str]:
    variants = [s]
    m = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", s)
    if m:
        y, mo, d = m.groups()
        variants.extend([
            f"{y}-{int(mo):02d}-{int(d):02d}",
            f"{y}/{int(mo):02d}/{int(d):02d}",
            f"{y}{int(mo):02d}{int(d):02d}",
        ])
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        variants.extend([
            f"{y}年{int(mo)}月{int(d)}日",
            f"{y}{int(mo):02d}{int(d):02d}",
        ])
    return variants


def _fact_variants(s: str) -> List[str]:
    variants = _date_variants(s)
    generic_terms = (
        "运载火箭", "火箭", "rocket",
        "航天发射场", "发射场", "cosmodrome", "launchsite",
    )
    for term in generic_terms:
        if term in s.lower():
            variants.append(re.sub(term, "", s, flags=re.I))
        if term in s:
            variants.append(s.replace(term, ""))
    return variants


def _flatten(value) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, dict):
        for v in value.values():
            yield from _flatten(v)
    elif isinstance(value, list):
        for v in value:
            yield from _flatten(v)
    else:
        text = str(value).strip()
        if text:
            yield text


def _facts(answer_gt: str) -> List[str]:
    try:
        parsed = json.loads(answer_gt)
    except Exception:
        parsed = None
    if parsed is not None:
        facts = list(_flatten(parsed))
    else:
        facts = [x.strip() for x in re.split(r"[，,；;|]\s*", answer_gt or "") if x.strip()]
    return [f for f in facts if _norm(f)]


def _required_sources(model_query: str) -> List[str]:
    try:
        parsed = json.loads(model_query)
    except Exception:
        return []
    if isinstance(parsed, dict):
        values = parsed.get("required_sources") or []
        return [str(v) for v in values if str(v).strip()]
    return []


def _contains_fact(pred: str, fact: str) -> bool:
    pred_norm = _norm(pred)
    for variant in _fact_variants(fact):
        fn = _norm(variant)
        if len(fn) >= 2 and fn in pred_norm:
            return True
    return False


def _num(s: str):
    try:
        return float(re.sub(r"[^0-9.\-]", "", s))
    except (ValueError, TypeError):
        return None


def verify(pred: str, answer_gt: str, model_query: str = "") -> Dict:
    facts = _facts(answer_gt)
    if not facts:
        return {"pass": False, "score": 0.0, "reason": "empty answer_gt"}

    if len(facts) == 1:
        pv, gv = _num(pred), _num(facts[0])
        if pv is not None and gv is not None and abs(pv - gv) < 1e-3:
            return {"pass": True, "score": 1.0, "reason": "numeric match"}

    missing = [fact for fact in facts if not _contains_fact(pred, fact)]
    if missing:
        return {"pass": False, "score": 0.0,
                "reason": "missing facts: " + "; ".join(missing[:5])}
    missing_sources = [src for src in _required_sources(model_query)
                       if _norm(src) not in _norm(pred)]
    if missing_sources:
        return {"pass": False, "score": 0.0,
                "reason": "missing sources: " + "; ".join(missing_sources[:5])}
    return {"pass": True, "score": 1.0,
            "reason": f"all {len(facts)} answer_gt facts matched"}


if __name__ == "__main__":
    gt = "1998年11月20日，Proton-K火箭，拜科努尔航天发射场"
    print(verify("1998-11-20 Proton-K Baikonur Cosmodrome", gt))
    print(verify("1998年11月20日 Proton-K 美国肯尼迪航天中心", gt))
