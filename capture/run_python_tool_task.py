"""Run a real §5.4/§5.5-style capture with a single `python` tool.

The script sends Anthropic-compatible /v1/messages requests to the configured
upstream, executes returned python tool calls locally, appends tool_result
messages, and writes a recorder-compatible raw_turns JSON file.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PYTHON_TOOL = {
    "name": "python",
    "description": (
        "Execute Python code for image processing. The code runs in a local workspace "
        "with Pillow available. The image attached in the user message is available "
        "at out/runtime/input_image.png. Write output files under assets/outputs/."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Write output files under assets/outputs/.",
            }
        },
        "required": ["code"],
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
    ext = path.suffix.lower().lstrip(".") or "png"
    media_type = "image/jpeg" if ext in {"jpg", "jpeg"} else "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def prepare_runtime_image(path: Path, root: Path) -> Path:
    runtime_dir = root / "out/runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    target = runtime_dir / "input_image.png"
    target.write_bytes(path.read_bytes())
    return target


def post_messages(base_url: str, auth_token: str, payload: dict) -> dict:
    url = base_url.rstrip("/") + "/v1/messages"
    req = Request(
        url,
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
            body = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail[:1000]}") from exc
    return json.loads(body)


def run_python(code: str, cwd: Path, timeout: int = 60) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    out = proc.stdout.strip()
    if proc.returncode != 0:
        return f"Python exited {proc.returncode}\n{out}"
    return out or "Done"


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
    ap.add_argument("--max-turns", type=int, default=100)
    args = ap.parse_args()

    root = Path.cwd()
    image_path = Path(args.image)
    prepare_runtime_image(image_path, root)
    settings = load_settings(Path(args.settings))
    base_url = settings["ANTHROPIC_BASE_URL"]
    auth_token = settings["ANTHROPIC_AUTH_TOKEN"]
    model = settings.get("ANTHROPIC_MODEL", "claude-opus-4-6")

    messages = [{
        "role": "user",
        "content": [
            image_block(image_path),
            {"type": "text", "text": args.prompt},
        ],
    }]

    last_output = []
    turn_count = 0
    for _ in range(args.max_turns):
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": messages,
            "tools": [PYTHON_TOOL],
        }
        resp = post_messages(base_url, auth_token, payload)
        content = resp.get("content", [])
        last_output = content
        turn_count += 1
        messages.append({"role": "assistant", "content": content})

        tool_uses = [b for b in content if b.get("type") == "tool_use" and b.get("name") == "python"]
        if not tool_uses:
            break
        results = []
        for tool in tool_uses:
            code = (tool.get("input") or {}).get("code", "")
            result = run_python(code, root)
            results.append({
                "type": "tool_result",
                "tool_use_id": tool.get("id"),
                "content": result,
            })
        messages.append({"role": "user", "content": results})

    if messages[-1].get("role") != "assistant" or not is_final_assistant(last_output):
        raise RuntimeError(
            f"failed_finalization: model did not return a natural final assistant "
            f"message within {args.max_turns} turns"
        )

    # recorder-compatible shape: full input history excludes final assistant,
    # final assistant lives in assistant_output.
    raw_messages = messages[:-1] if messages and messages[-1].get("role") == "assistant" else messages
    rec = {
        "task_id": uuid.uuid4().hex[:16],
        "model": model,
        "system": None,
        "tools": [PYTHON_TOOL],
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
