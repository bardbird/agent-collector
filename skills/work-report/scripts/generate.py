"""work-report 生成脚本。

用法: python generate.py --reporter 张三 --period 2026.04.14-2026.04.18 \
                         --theme "完成数据清洗工作" --out /tmp/zs.md
"""
from __future__ import annotations
import argparse
from pathlib import Path


def render(template: str, **kw) -> str:
    out = template
    for k, v in kw.items():
        out = out.replace("{{" + k + "}}", v or "(待补)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reporter", required=True)
    ap.add_argument("--period", required=True)
    ap.add_argument("--period-label", default="周报")
    ap.add_argument("--theme", default="")
    ap.add_argument("--outputs", default="")
    ap.add_argument("--risks", default="")
    ap.add_argument("--next-plan", default="")
    ap.add_argument("--template",
                    default=str(Path(__file__).resolve().parent.parent
                                / "assets" / "report_template.md"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    tpl = Path(a.template).read_text(encoding="utf-8")
    md = render(tpl,
                reporter=a.reporter, period=a.period,
                period_label=a.period_label, theme=a.theme,
                outputs=a.outputs, risks=a.risks, next_plan=a.next_plan)
    Path(a.out).write_text(md, encoding="utf-8")
    print(f"[work-report] -> {a.out}")


if __name__ == "__main__":
    main()
