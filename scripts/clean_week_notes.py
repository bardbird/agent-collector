"""scripts/clean_week_notes.py — Parse raw week-notes markdown into structured JSON.

Usage:
    python scripts/clean_week_notes.py samples/assets/data/week_notes.md -o out/week_notes_clean.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


METRIC_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(%|[a-zA-Z]*)\b")
RISK_PREFIXES = ("risk:", "risk ", "blocker:", "blocker ", "concern:")


def classify(text: str) -> str:
    lower = text.lower().strip().lstrip("- ").strip()
    if any(lower.startswith(p) for p in RISK_PREFIXES):
        return "risk"
    if METRIC_RE.search(text) and any(
        kw in lower for kw in ("pass rate", "reached", "reduced", "increased", "improved", "%")
    ):
        return "metric"
    return "accomplishment"


def extract_metrics(text: str) -> List[Dict[str, Any]]:
    out = []
    for m in METRIC_RE.finditer(text):
        value = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
        unit = m.group(2) if m.group(2) else None
        out.append({"value": value, "unit": unit})
    return out


def clean_text(text: str) -> str:
    text = text.strip().lstrip("- ").strip()
    for prefix in RISK_PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text


def parse_notes(raw: str) -> List[Dict[str, Any]]:
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.startswith("-"):
            continue
        category = classify(line)
        cleaned = clean_text(line)
        entry: Dict[str, Any] = {
            "raw": line.lstrip("- ").strip(),
            "text": cleaned,
            "category": category,
        }
        metrics = extract_metrics(line)
        if metrics:
            entry["metrics"] = metrics
        items.append(entry)
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean raw week-notes markdown into structured JSON")
    ap.add_argument("input", help="Path to raw week_notes.md")
    ap.add_argument("-o", "--output", default=None, help="Output JSON path (default: stdout)")
    args = ap.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8")
    items = parse_notes(raw)

    result = {
        "source": args.input,
        "item_count": len(items),
        "categories": sorted({i["category"] for i in items}),
        "items": items,
    }

    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"[clean] {len(items)} items -> {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
