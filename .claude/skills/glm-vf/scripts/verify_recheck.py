#!/usr/bin/env python3
"""glm-vf 验收脚本②｜verifier 正负双向测试（防恒真 / 防宽松）。

铁律:只跑正向 pass=True 不算通过——必须用负向(无关/空 pred)证明 pass=False,
否则判"恒真"退回(典型病灶:verifier 不依赖 pred,只检查磁盘上预置的标准答案)。

用法:
  python3 verify_recheck.py --item delivery/5.5_python_mm_rl --item delivery/5.7_search_rl
退出码 0=全部正负向行为正确, 1=存在恒真/宽松/正向失败。
"""
from __future__ import annotations
import argparse, importlib.util, json, os, sys


def load_v(p):
    s = importlib.util.spec_from_file_location("vmod", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def last_assistant(o):
    for m in reversed(o.get("messages", [])):
        if m.get("role") == "assistant" and m.get("content"):
            c = m["content"]
            return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
    return ""


def first_verifier(d):
    vd = os.path.join(d, "verifier")
    if not os.path.isdir(vd):
        return None
    for f in sorted(os.listdir(vd)):
        if f.endswith(".py") and not f.startswith("_"):
            return os.path.join(vd, f)
    return None


def call(v, pred, agt, mq):
    try:
        r = v.verify(pred, agt, mq)
        return r if isinstance(r, dict) else {"pass": None, "reason": f"非dict返回:{r!r}"}
    except Exception as e:
        return {"pass": None, "reason": f"verify()异常:{e}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", action="append", required=True, help="RL 分项目录(可多次)")
    a = ap.parse_args()
    alert = 0
    for d in a.item:
        name = os.path.basename(d.rstrip("/"))
        vf = first_verifier(d)
        jl = next((os.path.join(d, f) for f in os.listdir(d)
                   if f.endswith(".jsonl") and f.startswith("batch")), None)
        print("=" * 60)
        print(f"### {name}  verifier={os.path.basename(vf or '(无)')}")
        if not vf or not jl:
            print("  ⚠ RL 项缺 verifier/*.py 或 batch_*.jsonl"); alert += 1; continue
        v = load_v(vf)
        o = json.loads(open(jl, encoding="utf-8").readline())
        pred, agt, mq = last_assistant(o), o.get("answer_gt", ""), o.get("model_query", "")

        rp = call(v, pred, agt, mq)
        struct_ok = all(k in rp for k in ("pass", "score", "reason"))
        print(f"  正向(真实pred): pass={rp.get('pass')} score={rp.get('score')} 结构合法={struct_ok}")
        if rp.get("pass") is not True:
            print("  ⚠ 正向未 pass=True(真实答案都判错,verifier 失效)"); alert += 1

        for neg in ["", "我无法完成该任务,未产生任何输出或结果文件。"]:
            rn = call(v, neg, agt, mq)
            flag = "⚠恒真嫌疑!" if rn.get("pass") is True else "ok(负向正确判False)"
            print(f"  负向 pred={neg[:22]!r:24} pass={rn.get('pass')} → {flag}")
            if rn.get("pass") is True:
                alert += 1

    print(f"\n[_verifier] 恒真/宽松/正向失败计数 = {alert}  →  {'PASS' if alert == 0 else 'FAIL'}")
    sys.exit(0 if alert == 0 else 1)


if __name__ == "__main__":
    main()
