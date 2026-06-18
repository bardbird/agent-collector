"""§5.8 工具调用泛化 SFT — 转化器。

约束(出自需求文档 §5.8):
  · 工具白名单不固定;但 tools_used 必须命中 9 大场景标签之一(meta.scene)
  · 场景: 搜索 / 地图本地 / 电商 / 日程邮件 / 天气出行 / 表格数据 / 代码DevOps / 知识问答 / 设备控制 / 混合
  · meta.scene 必填, meta.tools_used 必填
  · mock 覆盖率交给 check_mock_coverage.py
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ALLOWED_SCENES = {
    "search", "map_local", "ecommerce", "calendar_email",
    "weather_travel", "table_data", "code_devops",
    "knowledge_qa", "device_control", "mixed",
}


def strict_extra(obj):
    errs = []
    meta = obj.get("meta") or {}
    if meta.get("scene") not in ALLOWED_SCENES:
        errs.append(f"5.8:meta.scene must be in {sorted(ALLOWED_SCENES)}")
    if not meta.get("tools_used"):
        errs.append("5.8:meta.tools_used missing")
    return errs


def meta_extra(obj, rec):
    used = common.tools_used(obj)
    return {"section": "5.8", "scene": "mixed", "tool_chain_length": len(used)}


def main():
    ap = argparse.ArgumentParser(description="§5.8 转化器(工具泛化 SFT)")
    ap.add_argument("--in", dest="indir", default="out/raw_turns")
    ap.add_argument("--out", default="out/jsonl/5_8")
    ap.add_argument("--images", default="out/images")
    a = ap.parse_args()
    stats = common.run_section("5_8", strict_extra, meta_extra,
                               a.indir, a.out, a.images)
    print(f"[5.8] {stats}")


if __name__ == "__main__":
    main()
