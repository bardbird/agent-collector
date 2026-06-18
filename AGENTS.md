# Repository Guidelines

## Project Structure & Module Organization

This repository captures Claude Code traffic and converts it to a Section 4.1 JSONL format.

- `proxy/recorder.py` is the mitmproxy addon that records `/v1/messages` I/O.
- `transform/to_section4_1.py` converts `out/raw_turns/` JSON into `out/jsonl/` JSONL and extracts images to `out/images/`.
- `dashboard/server.py` and `dashboard/index.html` provide the local capture dashboard.
- `start.sh` is the primary orchestration script; `run_proxy.sh` is a minimal direct proxy launcher.
- `out/` is generated runtime data and should not be committed.

## Build, Test, and Development Commands

Create a local environment and install the only Python dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
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
