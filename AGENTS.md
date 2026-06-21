# Repository Guidelines

## Project Structure & Module Organization

This repository captures Claude Code traffic and converts it to a Section 4.1 JSONL format.

- `proxy/recorder.py` is the mitmproxy addon that records `/v1/messages` I/O.
- `transform/to_section4_1.py` converts `out/raw_turns/` JSON into `out/jsonl/` JSONL and extracts images to `out/images/`.
- `dashboard/server.py` and `dashboard/index.html` provide the local capture dashboard.
- `start.sh` is the primary orchestration script; `run_proxy.sh` is a minimal direct proxy launcher.
- `out/` is generated runtime data and should not be committed.

## Build, Test, and Development Commands

Create the project environment with Python 3.12 and install declared dependencies:

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
```

Common commands:

```bash
./start.sh              # start the capture proxy on port 8080
./start.sh -d           # run the proxy in the background
./start.sh all          # run background proxy plus dashboard
./start.sh dash         # start dashboard only, default http://127.0.0.1:8765
./start.sh transform    # convert out/raw_turns/*.json to out/jsonl/*.jsonl
./start.sh stop         # stop the background proxy and flush captures
python3 transform/to_section4_1.py --in out/raw_turns --out out/jsonl --images out/images
```

To capture a session, run Claude Code with `ANTHROPIC_BASE_URL=http://127.0.0.1:8080 claude`.

## Coding Style & Naming Conventions

Use Python 3 standard-library patterns where possible. Keep modules script-friendly with `main()` entry points and small helpers. Follow 4-space indentation, `snake_case` for functions and variables, and uppercase constants such as `RAW_DIR`. Shell scripts should keep `set -euo pipefail` and quote variable expansions.

## Testing Guidelines

There is no automated test suite yet. For changes, run targeted smoke checks:

```bash
python3 transform/to_section4_1.py --in out/raw_turns --out out/jsonl --images out/images
python3 dashboard/server.py -p 9000
./start.sh status
```

When adding tests, place them under `tests/` as `test_*.py`. Prefer sanitized sample captures and assert tool-call pairing, image extraction, and final assistant-message handling.

## Commit & Pull Request Guidelines

Recent history uses concise Conventional Commit-style messages, including `feat(recorder): ...` and `fix: ...`. Keep commits focused and describe behavioral changes.

Pull requests should include a short summary, reproduction or validation commands, sample output paths when relevant, and screenshots for dashboard UI changes. Do not include API keys, raw private captures, or generated `out/` artifacts.

## Security & Configuration Tips

The recorder intentionally avoids writing request headers, but capture bodies may contain sensitive prompts, tool results, or files. Sanitize sample data before sharing. Use `PORT`, `DASH_PORT`, `UPSTREAM`, `CAPTURE_OUT`, and `IDLE_FLUSH_SEC` to override defaults without editing scripts.

## Production Discipline

Treat this local machine as production for collection, evaluation, and delivery work. Do not use temporary dependency downgrades, workaround environments, manual truncation, or quick-and-dirty runs as production or official results.

If the formal flow fails because of environment, dependency, interpreter, or toolchain mismatch, fix the declared environment first and rerun the formal flow. Do not bypass `requirements.txt`, lockfiles, project documents, task specs, or declared version constraints.

Never manually stop, truncate, or shorten long-running collection/evaluation jobs to fabricate completion. Use configured limits such as `max-turns`; if a run hits a limit or is interrupted, mark it invalid or incomplete.

Never inject fake user messages, assistant final answers, synthetic tool results, or post-hoc data to force a trajectory to look complete. Model final answers must be returned by the model itself.

Do not present smoke tests, debug runs, partial runs, or runs that violated declared flow/environment as official evaluation or production data. Label them explicitly as invalid/debug evidence.

For AI-managed data collection, the collection process must be agentic end-to-end under the formal project flow. If production requirements are ambiguous, resolve them from the project documents before running.

## Multimodal Capture

Multimodal inputs must be passed to the model as real message image blocks (`type: image` in raw Anthropic capture, transformed to `type: image_url` in delivered JSONL). Do not put local image paths into the user prompt as a substitute for image input.

When a local tool needs file access to the attached image, the capture driver must prepare a fixed runtime copy for the tool environment. That runtime path belongs in tool documentation or driver code, not in the natural user request.
