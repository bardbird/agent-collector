#!/usr/bin/env python3
"""glm-vf 验收脚本③｜mock 覆盖率复算 + skipped 审计。

关键严格点:覆盖率 100% 不够,必须确认 skipped=0。skipped>0 表示
check_mock_coverage 对"未在 mock 白名单的工具"静默跳过——若供应商漏录某工具
的 mock,覆盖率仍虚报 100%。本脚本解析 skipped 字段并显式告警。

用法:
  python3 mock_coverage.py --root delivery
退出码 0=全部 100% 且 skipped=0, 1=存在风险。
"""
from __future__ import annotations
import argparse, os, subprocess, sys


def iter_mock_items(root):
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isfile(os.path.join(d, "mock", "check_mock_coverage.py")):
            yield name, d


def parse(tok_line):
    skipped, miss, rate = 0, -1, 100.0
    for tok in tok_line.replace(",", " ").split():
        if tok.startswith("skipped"):
            try: skipped = int(tok.split("=")[1].split("(")[0])
            except Exception: pass
        if tok.startswith("miss"):
            try: miss = int(tok.split("=")[1])
            except Exception: pass
        if tok.startswith("rate"):
            try: rate = float(tok.split("=")[1].rstrip("%"))
            except Exception: pass
    return skipped, miss, rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True)
    a = ap.parse_args()
    risk = 0
    for root in a.root:
        for name, d in iter_mock_items(root):
            cc = os.path.join(d, "mock", "check_mock_coverage.py")
            db = os.path.join(d, "mock", "mock_responses.jsonl")
            miss_file = f"/tmp/glmvf_miss_{name}.jsonl"
            r = subprocess.run(["python3", cc, "--jsonl-root", d, "--db", db,
                                "--missing", miss_file], capture_output=True, text=True)
            out = (r.stdout or "").strip()
            print(f"### {name}")
            print("  " + out if out else f"  (无输出 exit={r.returncode}) {r.stderr.strip()}")
            skipped, miss, rate = parse(out)
            ok = (miss == 0 and skipped == 0 and rate == 100.0)
            if not ok:
                risk += 1
                print(f"  ⚠ 覆盖率风险: miss={miss} skipped={skipped} rate={rate}  "
                      f"(skipped>0 = 静默跳过未定义工具,覆盖率可能虚报)")
    print(f"\n[_mock_cov] 风险项 = {risk}  →  {'PASS' if risk == 0 else 'FAIL'}")
    sys.exit(0 if risk == 0 else 1)


if __name__ == "__main__":
    main()
