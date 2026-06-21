"""§5.9 tool generalization RL verifier.

Supports simple numeric answer_gt and structured JSON answer_gt. It also reads
model_query for required process/final-state facts, e.g. SKU and "not ordered".
"""
from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List


def _norm(s: str) -> str:
    return re.sub(r"[\s,，、。；;：:（）()\\[\\]【】\"'`*_\\-]+", "", (s or "").strip().lower())


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


def _json_facts(answer_gt: str) -> List[str]:
    try:
        parsed = json.loads(answer_gt)
    except Exception:
        return []
    if isinstance(parsed, dict):
        return list(_flatten(parsed))
    if isinstance(parsed, list):
        return list(_flatten(parsed))
    return [str(parsed)]


def _contains_number(pred: str, number: str) -> bool:
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return False
    pattern = r"(?<!\d)" + re.escape(digits[:-3]) + r",?" + re.escape(digits[-3:]) + r"(?!\d)"
    return bool(re.search(pattern, pred or ""))


def _extract_required_facts(answer_gt: str, model_query: str) -> List[str]:
    facts = _json_facts(answer_gt)
    if not facts and answer_gt:
        facts.append(answer_gt)

    # Common §5.9 exact final-state checks in model_query.
    for sku in re.findall(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b", model_query or ""):
        facts.append(sku)
    if re.search(r"未下单|没有下单|不要下单|not\s+ordered|did\s+not\s+order", model_query or "", re.I):
        facts.append("__NOT_ORDERED__")
    return facts


def _fact_ok(pred: str, fact: str) -> bool:
    if fact == "__NOT_ORDERED__":
        p = _norm(pred)
        negative = any(x in p for x in ("未下单", "没有下单", "未生成订单", "notordered", "didnotorder", "quoteonly"))
        positive_bad = any(x in p for x in ("已下单", "下单成功", "orderplaced", "ordered"))
        return negative and not positive_bad

    if re.fullmatch(r"[\d,]+(?:\.\d+)?", fact.strip()):
        return _contains_number(pred, fact)
    return _norm(fact) in _norm(pred)


def verify(pred: str, answer_gt: str, model_query: str = "") -> Dict:
    facts = [f for f in _extract_required_facts(answer_gt, model_query) if str(f).strip()]
    if not facts:
        return {"pass": False, "score": 0.0, "reason": "empty answer_gt"}

    missing = [str(f) for f in facts if not _fact_ok(pred, str(f))]
    if missing:
        return {"pass": False, "score": 0.0,
                "reason": "missing facts: " + "; ".join(missing[:5])}
    return {"pass": True, "score": 1.0,
            "reason": f"all {len(facts)} required facts matched"}


if __name__ == "__main__":
    q = "判断模型最终报价是否选择 SKU ABP3-MALL-001，且最低到手价为 1179 元，并明确没有下单。回答 YES 或 NO。"
    print(verify("SKU ABP3-MALL-001 到手价 ¥1,179，未下单。", "1179", q))
    print(verify("SKU ABP3-MARKET-017 到手价 ¥1,179，未下单。", "1179", q))
