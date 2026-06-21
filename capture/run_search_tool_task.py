"""Run a real §5.6 multimodal search capture with local mock tools.

The model sees image_search / web_search / image_zoom_in tools. This script
executes those tools locally, records mock responses, and writes recorder-
compatible raw_turns JSON through the normal proxy path.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


TOOLS = [
    {
        "name": "image_search",
        "description": "图片搜索工具。输入图片索引，识别主体并返回相关实体名称和标题。",
        "input_schema": {
            "type": "object",
            "properties": {"img_idx": {"type": "integer", "description": "图片在对话中的索引（从0开始）"}},
            "required": ["img_idx"],
        },
    },
    {
        "name": "web_search",
        "description": "联网搜索工具。输入搜索关键词，返回搜索结果。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
    },
    {
        "name": "image_zoom_in",
        "description": "图片局部放大工具。裁剪并放大指定区域。",
        "input_schema": {
            "type": "object",
            "properties": {
                "bbox_2d": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "边界框 [x1,y1,x2,y2]，坐标 0-1000",
                },
                "label": {"type": "string", "description": "目标物体名称"},
                "img_idx": {"type": "integer", "description": "图片索引"},
            },
            "required": ["bbox_2d", "label", "img_idx"],
        },
    },
]


FROZEN_EVIDENCE = {
    "apollo": {
        "image_search": {
            "query": "Apollo 11 Command Module Columbia",
            "provider": "frozen_curated_nasa_smithsonian",
            "fetched_at": 0,
            "entities": [
                {
                    "name": "Apollo 11 Command Module Columbia",
                    "type": "curated_image_entity",
                    "confidence": 0.99,
                    "description": "The exhibit card identifies the object as Apollo 11 Command Module Columbia, serial CM-107, with crew Armstrong, Aldrin, Collins and catalog A19700102000.",
                    "url": "mock://apollo/image-entity/columbia-command-module",
                }
            ],
        },
        "web_search": [
            {
                "match": ("catalog", "a19700102000", "smithsonian", "columbia", "cm-107"),
                "response": {
                    "provider": "frozen_curated_smithsonian",
                    "results": [
                        {
                            "title": "Smithsonian National Air and Space Museum - Apollo 11 Command Module Columbia",
                            "snippet": "The collection record identifies the Apollo 11 Command Module Columbia as object A19700102000. The command module is serial number CM-107 and was the crew compartment for Armstrong, Aldrin, and Collins.",
                            "url": "mock://smithsonian/collection/A19700102000",
                            "source": "curated_smithsonian",
                        }
                    ],
                },
            },
            {
                "match": ("apollo 11", "role", "command module", "mission", "cm-107"),
                "response": {
                    "provider": "frozen_curated_nasa",
                    "results": [
                        {
                            "title": "NASA Apollo 11 Mission - Command and Service Module",
                            "snippet": "Apollo 11 used command module Columbia as the crew cabin and the only spacecraft module that returned astronauts to Earth after the lunar landing mission.",
                            "url": "mock://nasa/apollo-11/command-module-columbia",
                            "source": "curated_nasa",
                        }
                    ],
                },
            },
            {
                "match": ("destination moon", "gallery", "exhibition", "display", "current"),
                "response": {
                    "provider": "frozen_curated_nasm",
                    "results": [
                        {
                            "title": "National Air and Space Museum - Destination Moon",
                            "snippet": "Destination Moon presents the Apollo 11 mission with Command Module Columbia as a central artifact in the museum's lunar exploration gallery context.",
                            "url": "mock://nasm/exhibitions/destination-moon",
                            "source": "curated_nasm",
                        }
                    ],
                },
            },
        ],
    },
    "zarya": {
        "image_search": {
            "query": "Zarya Functional Cargo Block",
            "provider": "frozen_curated_nasa_iss",
            "fetched_at": 0,
            "entities": [
                {
                    "name": "Zarya / Functional Cargo Block",
                    "type": "curated_image_entity",
                    "confidence": 0.98,
                    "description": "The panel identifies Zarya, also called FGB, as the first ISS module and links it to early power, propulsion, and guidance.",
                    "url": "mock://iss/image-entity/zarya-fgb",
                }
            ],
        },
        "web_search": [
            {
                "match": ("zarya", "fgb", "name", "functional cargo block", "module"),
                "response": {
                    "provider": "frozen_curated_nasa",
                    "results": [
                        {
                            "title": "NASA ISS Assembly - Zarya Functional Cargo Block",
                            "snippet": "Zarya is the Russian-built Functional Cargo Block, or FGB, and was the first module of the International Space Station.",
                            "url": "mock://nasa/iss/zarya-functional-cargo-block",
                            "source": "curated_nasa",
                        }
                    ],
                },
            },
            {
                "match": ("zarya", "launch date", "20 november 1998", "proton-k"),
                "response": {
                    "provider": "frozen_curated_esa",
                    "results": [
                        {
                            "title": "ESA ISS Assembly Sequence - Zarya Launch",
                            "snippet": "Zarya was launched on 20 November 1998 on a Proton-K launch vehicle as the first element of the ISS assembly sequence.",
                            "url": "mock://esa/iss/assembly/zarya-launch",
                            "source": "curated_esa",
                        }
                    ],
                },
            },
            {
                "match": ("baikonur", "launch site", "cosmodrome", "proton-k", "zarya"),
                "response": {
                    "provider": "frozen_curated_roscosmos",
                    "results": [
                        {
                            "title": "ISS First Element Launch Record",
                            "snippet": "The Zarya/FGB module lifted off from Baikonur Cosmodrome aboard a Proton-K rocket on 20 November 1998.",
                            "url": "mock://roscosmos/iss/zarya-baikonur-proton-k",
                            "source": "curated_roscosmos",
                        }
                    ],
                },
            },
        ],
    },
}


def load_settings(path: Path) -> dict:
    settings: dict = {}
    for p in (Path.home() / ".claude/settings.json", Path.home() / ".claude/settings.local.json"):
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        settings.update(data.get("env", data))
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        settings.update(data.get("env", data))
    return settings


def image_block(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    media_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def req_hash(tool_name: str, arguments: dict) -> str:
    raw = tool_name + json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_mock(path: Path, tool_name: str, arguments: dict, response: dict | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "request_hash": req_hash(tool_name, arguments),
        "tool_name": tool_name,
        "request": arguments,
        "response": response,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def fetch_json(url: str, timeout: int = 20) -> dict:
    req = Request(url, headers={"user-agent": "agent-collector/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_text(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"user-agent": "Mozilla/5.0 agent-collector/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_html_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def wikipedia_search(query: str, limit: int = 5) -> list[dict]:
    params = urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": str(limit),
        "utf8": "1",
    })
    data = fetch_json(f"https://en.wikipedia.org/w/api.php?{params}")
    out = []
    for item in (data.get("query") or {}).get("search", []):
        title = item.get("title", "")
        out.append({
            "title": title,
            "snippet": clean_html_text(item.get("snippet", "")),
            "url": f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
            "source": "wikipedia_api",
        })
    return out


def duckduckgo_search(query: str, limit: int = 5) -> list[dict]:
    text = fetch_text(f"https://duckduckgo.com/html/?q={quote(query)}")
    results = []
    blocks = re.split(r'<div class="result results_links', text)
    for block in blocks[1:]:
        m = re.search(r'class="result__a" href="([^"]+)".*?>(.*?)</a>', block, re.S)
        if not m:
            continue
        sn = re.search(r'class="result__snippet".*?>(.*?)</a>|class="result__snippet".*?>(.*?)</div>', block, re.S)
        snippet = clean_html_text((sn.group(1) or sn.group(2)) if sn else "")
        results.append({
            "title": clean_html_text(m.group(2)),
            "snippet": snippet,
            "url": html.unescape(m.group(1)),
            "source": "duckduckgo_html",
        })
        if len(results) >= limit:
            break
    return results


def live_web_search(query: str) -> dict:
    results = []
    errors = []
    try:
        results.extend(wikipedia_search(query, limit=4))
    except Exception as exc:
        errors.append({"provider": "wikipedia_api", "error": f"{type(exc).__name__}: {exc}"})
    try:
        ddg = duckduckgo_search(query, limit=4)
    except Exception as exc:
        ddg = []
        errors.append({"provider": "duckduckgo_html", "error": f"{type(exc).__name__}: {exc}"})
    seen = {r.get("url") for r in results}
    for item in ddg:
        if item.get("url") not in seen:
            results.append(item)
            seen.add(item.get("url"))
    return {
        "query": query,
        "provider": "wikipedia_api+duckduckgo_html",
        "fetched_at": int(time.time()),
        "errors": errors,
        "empty": not bool(results),
        "results": results[:6],
    }


def live_image_search(scenario: str) -> dict:
    if scenario == "zarya":
        query = "Zarya Functional Cargo Block"
        provider_url = "https://images-api.nasa.gov/search?q=Zarya%20Functional%20Cargo%20Block&media_type=image"
    else:
        query = "Apollo 11 Command Module Columbia"
        provider_url = "https://images-api.nasa.gov/search?q=Apollo%2011%20Command%20Module%20Columbia&media_type=image"
    data = fetch_json(provider_url)
    entities = []
    items = (data.get("collection") or {}).get("items", [])[:5]
    for item in items:
        meta = (item.get("data") or [{}])[0]
        title = meta.get("title") or meta.get("description", "")[:80]
        entities.append({
            "name": title,
            "type": "nasa_image_result",
            "confidence": None,
            "description": clean_html_text(meta.get("description", ""))[:400],
            "url": item.get("href", ""),
            "date_created": meta.get("date_created", ""),
        })
    return {
        "query": query,
        "provider": "nasa_images_api",
        "fetched_at": int(time.time()),
        "entities": entities,
        "caption": f"NASA Images search results for {query}",
    }


def frozen_web_search(query: str, scenario: str) -> dict:
    q = query.lower()
    evidence = FROZEN_EVIDENCE[scenario]["web_search"]
    scored = []
    for item in evidence:
        score = sum(1 for term in item["match"] if term in q)
        if score:
            scored.append((score, item["response"]))
    if not scored:
        scored = [(0, evidence[0]["response"])]
    results = []
    provider = "frozen_curated"
    for _, response in sorted(scored, key=lambda x: x[0], reverse=True)[:2]:
        provider = response.get("provider", provider)
        results.extend(response.get("results", []))
    return {
        "query": query,
        "provider": provider,
        "fetched_at": 0,
        "errors": [],
        "empty": False,
        "results": results[:4],
    }


def execute_tool(tool_name: str, arguments: dict, mock_db: Path, scenario: str = "apollo",
                 evidence_mode: str = "frozen") -> str:
    if tool_name == "image_search":
        if evidence_mode == "frozen":
            response = FROZEN_EVIDENCE[scenario]["image_search"]
        else:
            response = live_image_search(scenario)
    elif tool_name == "image_zoom_in":
        label = arguments.get("label", "")
        label_blob = json.dumps(arguments, ensure_ascii=False).lower()
        if "zarya" in label_blob or "fgb" in label_blob:
            observation = "The panel text reads ZARYA, Functional Cargo Block, also called FGB, First ISS module."
        elif "iss" in label_blob or "module" in label_blob or "模块" in label:
            observation = "The side label states First ISS module and role: early power, propulsion & guidance."
        elif "catalog" in label.lower() or "编号" in label or "catalog" in label_blob:
            observation = "The lower exhibit label reads Catalog: A19700102000."
        elif "crew" in label.lower() or "船员" in label:
            observation = "The crew line reads Armstrong, Aldrin, Collins."
        elif "cm" in label.lower() or "107" in label:
            observation = "The identifier on the label reads CM-107."
        else:
            observation = "The main label reads Apollo 11 Command Module Columbia."
        response = {
            "crop_id": "zoom_multimodal_search_label_001",
            "label": label,
            "observation": observation,
        }
    elif tool_name == "web_search":
        query = arguments.get("query", "")
        if evidence_mode == "frozen":
            response = frozen_web_search(query, scenario)
        else:
            response = live_web_search(query)
    else:
        response = {"error": f"unknown tool {tool_name}"}
    append_mock(mock_db, tool_name, arguments, response)
    return json.dumps(response, ensure_ascii=False)


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
    try:
        with urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:1000]}") from exc


def is_final_assistant(content: list) -> bool:
    has_tool_use = any(b.get("type") == "tool_use" for b in content)
    has_text = any(b.get("type") == "text" and b.get("text", "").strip() for b in content)
    return has_text and not has_tool_use


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default="out/capture.settings.json")
    ap.add_argument("--image", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", default="out/raw_turns")
    ap.add_argument("--mock-db", default="mock/mock_responses.jsonl")
    ap.add_argument("--max-turns", type=int, default=100)
    ap.add_argument("--scenario", choices=["apollo", "zarya"], default="apollo")
    ap.add_argument("--evidence-mode", choices=["frozen", "live"], default="frozen")
    args = ap.parse_args()

    settings = load_settings(Path(args.settings))
    base_url = settings["ANTHROPIC_BASE_URL"]
    auth_token = settings["ANTHROPIC_AUTH_TOKEN"]
    model = settings.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    mock_db = Path(args.mock_db)

    system_prompt = (
        "你是一个具备联网搜索、图片搜索和图像局部放大能力的 AI 助手。"
        "回答多模态搜索问题时，要把搜索意图识别、检索词改写、工具检索依据、证据整合和最终答案表达清楚。"
        "引用证据时使用来源标题或URL。"
    )
    messages = [{
        "role": "user",
        "content": [
            image_block(Path(args.image)),
            {"type": "text", "text": args.prompt},
        ],
    }]

    last_output = []
    turn_count = 0
    for _ in range(args.max_turns):
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "tools": TOOLS,
            "messages": messages,
        }
        resp = post_messages(base_url, auth_token, payload)
        content = resp.get("content", [])
        last_output = content
        turn_count += 1
        messages.append({"role": "assistant", "content": content})
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if not tool_uses:
            break
        results = []
        for tool in tool_uses:
            result = execute_tool(tool.get("name", ""), tool.get("input") or {}, mock_db,
                                  args.scenario, args.evidence_mode)
            if args.evidence_mode == "live" and tool.get("name") in {"web_search", "image_search"}:
                time.sleep(1.0)
            results.append({"type": "tool_result", "tool_use_id": tool.get("id"), "content": result})
        messages.append({"role": "user", "content": results})

    if messages[-1].get("role") != "assistant" or not is_final_assistant(last_output):
        raise RuntimeError(
            f"failed_finalization: model did not return a natural final assistant "
            f"message within {args.max_turns} turns"
        )

    raw_messages = messages[:-1] if messages and messages[-1].get("role") == "assistant" else messages
    rec = {
        "task_id": uuid.uuid4().hex[:16],
        "model": model,
        "system": system_prompt,
        "tools": TOOLS,
        "messages": raw_messages,
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
