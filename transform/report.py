"""transform/report.py — 多样性 + 通过率汇总。

扫描 out/jsonl/<5_x>/*.jsonl,产出 out/report.md:
  · 每分项 accepted / rejected 计数
  · 每分项 §4.4 多样性(轮次桶 / 工具组合数 / zh 比例 / 反思比例)
  · _rejected.jsonl 的 top 错因
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

import common


SECTIONS = ["5_1", "5_2", "5_3", "5_4", "5_5", "5_6", "5_7", "5_8", "5_9"]


def load_jsonl(p: Path):
    out = []
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            out.append(json.loads(ln))
    return out


def section_block(root: Path, sec: str) -> str:
    acc = load_jsonl(root / sec / f"{sec}.jsonl")
    rej = load_jsonl(root / sec / "_rejected.jsonl")
    total = len(acc) + len(rej)
    if total == 0:
        return f"## §{sec.replace('_','.')}\n\n_无数据_\n"
    rate = len(acc) / total * 100
    div = common.diversity_report(acc) if acc else {"total": 0}

    top_errs = Counter()
    for r in rej:
        for e in r.get("errors", []):
            top_errs[e.split(":", 2)[1] if ":" in e else e] += 1

    lines = [f"## §{sec.replace('_','.')}",
             "",
             f"- 通过 / 总 = **{len(acc)} / {total}** ({rate:.1f}%)",
             f"- 多样性: {json.dumps(div, ensure_ascii=False)}",
             ""]
    if top_errs:
        lines.append("**Top 5 拒因**:")
        for e, n in top_errs.most_common(5):
            lines.append(f"  - {e} × {n}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl-root", default="out/jsonl")
    ap.add_argument("--out", default="out/report.md")
    a = ap.parse_args()

    root = Path(a.jsonl_root)
    parts = ["# 多样性 / 通过率报告", ""]
    for s in SECTIONS:
        parts.append(section_block(root, s))
    Path(a.out).write_text("\n".join(parts), encoding="utf-8")
    print(f"[report] -> {a.out}")


if __name__ == "__main__":
    main()
