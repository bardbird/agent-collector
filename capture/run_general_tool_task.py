"""Run real §5.8/§5.9 generic tool-calling captures.

The model receives scenario-specific tool schemas through Anthropic messages.
This driver executes the returned tool_use blocks, records every request and
response into mock_responses.jsonl, and writes recorder-compatible raw_turns.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen


TOOLS_5_8 = [
    {
        "name": "venue_options_read",
        "description": "读取用户提供的活动场地图，返回可用区域和容量线索。",
        "input_schema": {
            "type": "object",
            "properties": {"img_idx": {"type": "integer", "description": "图片索引"}},
            "required": ["img_idx"],
        },
    },
    {
        "name": "weather_query",
        "description": "查询指定城市指定日期的天气预报。",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["city", "date"],
        },
    },
    {
        "name": "room_availability",
        "description": "查询指定日期和人数的会议/活动空间可用性。",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "date": {"type": "string"},
                "attendees": {"type": "integer"},
                "needs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["city", "date", "attendees"],
        },
    },
    {
        "name": "calendar_create",
        "description": "创建日历事件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "integer"},
                "reminder_minutes": {"type": "integer"},
            },
            "required": ["title", "start_time", "end_time", "location"],
        },
    },
    {
        "name": "email_send",
        "description": "发送邮件通知。",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
]


TOOLS_5_9 = [
    {
        "name": "product_search",
        "description": "按关键词检索商品候选。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "ship_to": {"type": "string"}},
            "required": ["query", "ship_to"],
        },
    },
    {
        "name": "inventory_check",
        "description": "查询商品库存和预计送达日期。",
        "input_schema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}, "ship_to": {"type": "string"}},
            "required": ["sku", "ship_to"],
        },
    },
    {
        "name": "coupon_apply",
        "description": "试算指定商品的可用优惠。",
        "input_schema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}, "coupon_code": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "price_compare",
        "description": "比较候选商品的到手价。",
        "input_schema": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sku": {"type": "string"},
                            "price": {"type": "number"},
                            "shipping": {"type": "number"},
                            "discount": {"type": "number"},
                        },
                        "required": ["sku", "price", "shipping", "discount"],
                    },
                }
            },
            "required": ["candidates"],
        },
    },
    {
        "name": "order_quote",
        "description": "生成订单报价但不下单。",
        "input_schema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}, "ship_to": {"type": "string"}},
            "required": ["sku", "ship_to"],
        },
    },
]


def load_settings(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("env", data)


def image_block(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    media_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def req_hash(tool_name: str, arguments: dict) -> str:
    raw = tool_name + json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_mock(path: Path, tool_name: str, arguments: dict, response: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "request_hash": req_hash(tool_name, arguments),
        "tool_name": tool_name,
        "request": arguments,
        "response": response,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def execute_5_8(tool: str, args: dict) -> dict:
    if tool == "venue_options_read":
        return {
            "source": "local_image_analysis",
            "areas": [
                {"name": "Outdoor Lawn", "capacity": 42, "risk": "weather_exposed"},
                {"name": "Indoor Hall", "capacity": 36, "risk": "requires_booking"},
            ],
            "note": "The image shows a separate outdoor lawn and indoor hall option.",
        }
    if tool == "weather_query":
        return {
            "source": "open_meteo_cached_live_fixture",
            "city": args.get("city"),
            "date": args.get("date"),
            "forecast": "rain",
            "rain_probability": 72,
            "temp_c": {"low": 21, "high": 27},
            "wind_kph": 18,
        }
    if tool == "room_availability":
        return {
            "source": "venue_inventory_live_fixture",
            "date": args.get("date"),
            "matches": [
                {"room": "Indoor Hall", "capacity": 36, "available": True, "slot": "15:00-17:00"},
                {"room": "Studio B", "capacity": 18, "available": False, "slot": None},
            ],
        }
    if tool == "calendar_create":
        return {
            "status": "created",
            "event_id": "evt_team_20260703_indoor_hall",
            "title": args.get("title"),
            "location": args.get("location"),
            "start_time": args.get("start_time"),
            "end_time": args.get("end_time"),
        }
    if tool == "email_send":
        return {
            "status": "sent",
            "message_id": "msg_team_activity_rain_plan",
            "to_count": len(args.get("to") or []),
            "subject": args.get("subject"),
        }
    return {"error": f"unknown tool {tool}"}


def execute_5_9(tool: str, args: dict) -> dict:
    if tool == "product_search":
        return {
            "source": "merchant_catalog_snapshot",
            "results": [
                {"sku": "ABP3-MALL-001", "name": "AuroraBuds Pro 3", "seller": "Mall A", "price": 1299, "shipping": 0},
                {"sku": "ABP3-MARKET-017", "name": "AuroraBuds Pro 3", "seller": "Market B", "price": 1249, "shipping": 18},
                {"sku": "ABP3-OUTLET-009", "name": "AuroraBuds Pro 3", "seller": "Outlet C", "price": 1199, "shipping": 35},
            ],
        }
    if tool == "inventory_check":
        sku = args.get("sku")
        data = {
            "ABP3-MALL-001": {"in_stock": True, "delivery_date": "2026-06-20"},
            "ABP3-MARKET-017": {"in_stock": True, "delivery_date": "2026-06-19"},
            "ABP3-OUTLET-009": {"in_stock": False, "delivery_date": None},
        }
        return {"sku": sku, **data.get(sku, {"in_stock": False, "delivery_date": None})}
    if tool == "coupon_apply":
        sku = args.get("sku")
        discounts = {"ABP3-MALL-001": 120, "ABP3-MARKET-017": 60, "ABP3-OUTLET-009": 0}
        return {"sku": sku, "coupon_code": args.get("coupon_code") or "AUTO", "discount": discounts.get(sku, 0)}
    if tool == "price_compare":
        rows = []
        candidates = args.get("candidates") or []
        if isinstance(candidates, str):
            try:
                candidates = json.loads(candidates)
            except json.JSONDecodeError:
                candidates = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            total = float(c.get("price", 0)) + float(c.get("shipping", 0)) - float(c.get("discount", 0))
            rows.append({**c, "final_price": round(total, 2)})
        rows.sort(key=lambda x: x["final_price"])
        return {"ranked": rows, "cheapest_sku": rows[0]["sku"] if rows else None}
    if tool == "order_quote":
        quotes = {
            "ABP3-MALL-001": {"quote_id": "quote_abp3_mall_001_shanghai", "final_price": 1179, "delivery_date": "2026-06-20"},
            "ABP3-MARKET-017": {"quote_id": "quote_abp3_market_017_shanghai", "final_price": 1207, "delivery_date": "2026-06-19"},
        }
        q = quotes.get(args.get("sku"), {"quote_id": "quote_unknown", "final_price": None, "delivery_date": None})
        return {
            "quote_id": q["quote_id"],
            "sku": args.get("sku"),
            "ship_to": args.get("ship_to"),
            "final_price": q["final_price"],
            "currency": "CNY",
            "delivery_date": q["delivery_date"],
        }
    return {"error": f"unknown tool {tool}"}


def post_messages(base_url: str, auth_token: str, payload: dict) -> dict:
    req = Request(
        base_url.rstrip("/") + "/v1/messages",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "authorization": f"Bearer {auth_token}",
            "x-api-key": auth_token,
            "user-agent": "claude-code",
        },
        method="POST",
    )
    with urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default="out/capture.settings.json")
    ap.add_argument("--section", choices=["5.8", "5.9"], required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--image")
    ap.add_argument("--out", default="out/raw_turns")
    ap.add_argument("--mock-db", default="mock/mock_responses.jsonl")
    ap.add_argument("--max-turns", type=int, default=8)
    args = ap.parse_args()

    settings = load_settings(Path(args.settings))
    base_url = settings["ANTHROPIC_BASE_URL"]
    auth_token = settings["ANTHROPIC_AUTH_TOKEN"]
    model = settings.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    mock_db = Path(args.mock_db)
    tools = TOOLS_5_8 if args.section == "5.8" else TOOLS_5_9
    executor = execute_5_8 if args.section == "5.8" else execute_5_9
    system_prompt = "你是一个能根据任务目标选择并串联工具完成工作的 Agent。不要调用无关工具，信息足够时及时给最终答案。"
    content = []
    if args.image:
        content.append(image_block(Path(args.image)))
    content.append({"type": "text", "text": args.prompt})
    messages = [{"role": "user", "content": content}]

    last_output = []
    turn_count = 0
    for _ in range(args.max_turns):
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "tools": tools,
            "messages": messages,
        }
        resp = post_messages(base_url, auth_token, payload)
        blocks = resp.get("content", [])
        last_output = blocks
        turn_count += 1
        messages.append({"role": "assistant", "content": blocks})
        tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
        if not tool_uses:
            break
        results = []
        for tu in tool_uses:
            tool_name = tu.get("name", "")
            tool_args = tu.get("input") or {}
            response = executor(tool_name, tool_args)
            append_mock(mock_db, tool_name, tool_args, response)
            results.append({"type": "tool_result", "tool_use_id": tu.get("id"), "content": json.dumps(response, ensure_ascii=False)})
        messages.append({"role": "user", "content": results})

    rec = {
        "task_id": uuid.uuid4().hex[:16],
        "model": model,
        "system": system_prompt,
        "tools": tools,
        "messages": messages[:-1] if messages and messages[-1].get("role") == "assistant" else messages,
        "assistant_output": last_output,
        "turn_count": turn_count,
        "captured_at": int(time.time()),
        "raw": {"request": {"url": base_url.rstrip("/") + "/v1/messages"}, "response": {}},
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{rec['task_id']}.json"
    out_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
