#!/usr/bin/env python3
"""glm-vf 验收脚本④｜mock_server 端到端:确定性 + 未命中 404。

启动各分项 mock_server,逐条回放 mock_responses.jsonl,验证"同一 request 返回
同一 response"(确定性),并验证未命中返回 404(§C.2)。

用法:
  python3 mock_server_e2e.py --root delivery
退出码 0=全部一致且 404 正常, 1=存在不一致/无 404。
"""
from __future__ import annotations
import argparse, json, os, subprocess, time, urllib.request, urllib.error, sys


def iter_mock_items(root):
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isfile(os.path.join(d, "mock", "mock_server.py")):
            yield name, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True)
    a = ap.parse_args()
    fail = 0
    for root in a.root:
        for idx, (name, d) in enumerate(iter_mock_items(root)):
            srv = os.path.join(d, "mock", "mock_server.py")
            db = os.path.join(d, "mock", "mock_responses.jsonl")
            port = 9000 + idx
            recs = [json.loads(l) for l in open(db, encoding="utf-8") if l.strip()]
            print(f"### {name}: {len(recs)} 条 mock")
            p = subprocess.Popen(["python3", srv, "--data", db, "--port", str(port)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            time.sleep(1.2)
            identical, miss_ok = 0, False
            try:
                for r in recs:
                    body = json.dumps({"arguments": r["request"]}).encode()
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/mock/{r['tool_name']}",
                        data=body, headers={"Content-Type": "application/json"})
                    try:
                        got = json.loads(urllib.request.urlopen(req, timeout=3).read())
                        identical += int(got == r["response"])
                    except Exception as e:
                        print(f"  ✗ {r['tool_name']} 请求异常 {e}")
                try:
                    urllib.request.urlopen(urllib.request.Request(
                        f"http://127.0.0.1:{port}/mock/web_search",
                        data=json.dumps({"arguments": {"query": "__no_such__"}}).encode(),
                        headers={"Content-Type": "application/json"}), timeout=3)
                except urllib.error.HTTPError as e:
                    miss_ok = (e.code == 404)
                print(f"  一致性 {identical}/{len(recs)}；未命中404={miss_ok}")
                if identical != len(recs) or not miss_ok:
                    fail += 1
            finally:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except Exception:
                    p.kill()
    print(f"\n[_mock_e2e] 不一致/无404 项 = {fail}  →  {'PASS' if fail == 0 else 'FAIL'}")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
