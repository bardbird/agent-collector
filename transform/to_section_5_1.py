"""§5.1 Skills SFT 轨迹数据 — 转化器。

约束(出自需求文档 §5.1 + §4.1/§4.2/§4.4):
  · 工具白名单: {Skill, AskUserQuestion}
  · 必须含 <system-reminder> 注入 skills 列表(放在 user content 头部)
  · meta.skill_name 必填
  · 轨迹 ≥ 4 轮 tool_call+tool_response
  · 末条 assistant
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

WHITELIST = ["Skill", "AskUserQuestion"]


def _has_system_reminder_in_user(obj):
    for m in obj.get("messages", []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str) and "<system-reminder>" in c:
            return True
        if isinstance(c, list):
            for b in c:
                if b.get("type") == "text" and "<system-reminder>" in b.get("text", ""):
                    return True
    return False


def strict_extra(obj):
    errs = []
    if not _has_system_reminder_in_user(obj):
        errs.append("5.1:no <system-reminder> in any user message (must inject skills list)")
    if not (obj.get("meta") or {}).get("skill_name"):
        errs.append("5.1:meta.skill_name missing")
    return errs


def meta_extra(obj, rec):
    # skill_name: 从首个 Skill 调用的 arguments.skill 字段取
    for m in obj.get("messages", []):
        for c in m.get("tool_calls") or []:
            if (c.get("function") or {}).get("name") == "Skill":
                try:
                    args = json.loads(c["function"]["arguments"])
                    if args.get("skill"):
                        return {"skill_name": args["skill"], "section": "5.1"}
                except Exception:
                    pass
    return {"section": "5.1"}


def main():
    ap = argparse.ArgumentParser(description="§5.1 转化器")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_1")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_1", strict_extra, meta_extra,
                               a.indir, a.out, a.images, whitelist=WHITELIST)
    print(f"[5.1] {stats}")


if __name__ == "__main__":
    main()
