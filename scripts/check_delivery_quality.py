"""Repository-level delivery quality checks.

Checks all delivery/*/batch*.jsonl files and package manifests/reports for:
  - no production-chain metadata in sample meta
  - no production-chain metadata in package manifest/report files
  - verifier positive and negative cases for RL packages with verifier/
  - mock coverage for packages with mock/
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_META = {"source", "model", "collection_run", "delivery_package"}
FORBIDDEN_PACKAGE_KEYS = {
    "source",
    "source_run",
    "source_raw",
    "model",
    "collection_run",
    "delivery_package",
}
FORBIDDEN_REPORT_TEXT = (
    "source_run",
    "source_raw",
    "meta.source",
    "meta.model",
    "claude-opus",
    "claude-code-capture",
    "collection_run",
    "delivery_package",
)
FORBIDDEN_JSONL_TEXT = (
    "samples/assets/",
    "out/raw_turns",
    "out/formal_rerun",
)
LOCAL_TOOLS = "Skill,AskUserQuestion,Bash,python"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def final_answer(obj: dict[str, Any]) -> str:
    for msg in reversed(obj.get("messages", [])):
        if msg.get("role") == "assistant" and not msg.get("tool_calls"):
            return msg.get("content") or ""
    return ""


def tool_rounds(obj: dict[str, Any]) -> int:
    declared: set[str] = set()
    paired: set[str] = set()
    for msg in obj.get("messages", []):
        if msg.get("role") == "assistant":
            for call in msg.get("tool_calls") or []:
                cid = call.get("id")
                if cid:
                    declared.add(cid)
        elif msg.get("role") == "tool":
            tcid = msg.get("tool_call_id")
            if tcid in declared:
                paired.add(tcid)
    return len(paired)


def round_bucket(n: int) -> str:
    if 4 <= n <= 6:
        return "4-6"
    if 7 <= n <= 10:
        return "7-10"
    if n >= 11:
        return "11+"
    return "<4"


def load_verifier(path: Path):
    spec = importlib.util.spec_from_file_location("delivery_verifier", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verifier {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def negative_cases(section: str, obj: dict[str, Any]) -> list[tuple[str, str]]:
    if section == "5.5":
        return [
            ("empty", ""),
            ("unable", "我无法完成该任务，因为没有生成图片。"),
            ("missing_artifact", "输出文件：assets/outputs/not_created.png，尺寸 960 x 620，REWORK red badge"),
        ]
    if section == "5.7":
        return [
            ("empty", ""),
            ("missing_sources", "Zarya FGB Functional Cargo Block 1998年11月20日 Proton-K Baikonur Cosmodrome"),
            ("wrong_launch_site", "Zarya FGB Functional Cargo Block 1998年11月20日 Proton-K Kennedy Space Center"),
        ]
    if section == "5.9":
        return [
            ("empty", ""),
            ("wrong_sku", "SKU ABP3-MARKET-017 到手价 ¥1,179，未下单。"),
            ("ordered", "SKU ABP3-MALL-001 到手价 ¥1,179，已下单。"),
        ]
    return [("empty", "")]


def check_meta(pkg: Path, obj: dict[str, Any], errors: list[str]) -> None:
    meta = obj.get("meta") or {}
    bad = sorted(k for k in FORBIDDEN_META if k in meta)
    if bad:
        errors.append(f"{pkg}: forbidden meta keys {bad}")


def check_jsonl_text(pkg: Path, obj: dict[str, Any], errors: list[str]) -> None:
    text = json.dumps(obj, ensure_ascii=False)
    bad = [needle for needle in FORBIDDEN_JSONL_TEXT if needle in text]
    if bad:
        errors.append(f"{pkg}: forbidden JSONL production/runtime text {bad}")


def check_rounds(pkg: Path, obj: dict[str, Any], errors: list[str]) -> int:
    rounds = tool_rounds(obj)
    if rounds < 4:
        errors.append(f"{pkg}: tool_rounds={rounds} < 4")
    return rounds


def find_forbidden_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_PACKAGE_KEYS:
                found.append(child_path)
            found.extend(find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            found.extend(find_forbidden_keys(child, f"{path}[{idx}]"))
    return found


def check_package_metadata(pkg: Path, errors: list[str]) -> None:
    manifest = pkg / "manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{pkg}: manifest invalid JSON: {exc}")
        else:
            bad = find_forbidden_keys(data)
            if bad:
                errors.append(f"{pkg}: forbidden manifest keys {bad}")

    for report in sorted(pkg.glob("report*.md")):
        text = report.read_text(encoding="utf-8")
        bad_text = [needle for needle in FORBIDDEN_REPORT_TEXT if needle in text]
        if bad_text:
            errors.append(f"{pkg}: forbidden report metadata text {bad_text}")


def check_verifier(pkg: Path, obj: dict[str, Any], errors: list[str]) -> None:
    verifier_dir = pkg / "verifier"
    if not verifier_dir.exists():
        return
    verifier_files = sorted(verifier_dir.glob("verifier_*.py"))
    if not verifier_files:
        errors.append(f"{pkg}: verifier directory exists but no verifier_*.py")
        return
    mod = load_verifier(verifier_files[0])
    answer_gt = obj.get("answer_gt") or ""
    model_query = obj.get("model_query") or ""
    positive = mod.verify(final_answer(obj), answer_gt, model_query)
    if not positive.get("pass"):
        errors.append(f"{pkg}: verifier positive failed: {positive}")
    section = (obj.get("meta") or {}).get("section", "")
    for name, pred in negative_cases(section, obj):
        res = mod.verify(pred, answer_gt, model_query)
        if res.get("pass"):
            errors.append(f"{pkg}: verifier negative '{name}' passed unexpectedly: {res}")


def check_mock(pkg: Path, errors: list[str]) -> None:
    mock_dir = pkg / "mock"
    db = mock_dir / "mock_responses.jsonl"
    checker = mock_dir / "check_mock_coverage.py"
    if not mock_dir.exists():
        return
    if not db.exists() or not checker.exists():
        errors.append(f"{pkg}: mock package missing db or checker")
        return
    missing = mock_dir / "_missing_mocks.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(checker),
            "--jsonl-root",
            str(pkg),
            "--db",
            str(db),
            "--missing",
            str(missing),
            "--local-tools",
            LOCAL_TOOLS,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        errors.append(f"{pkg}: mock coverage command failed: {proc.stdout.strip()}")
        return
    if missing.exists() and missing.read_text(encoding="utf-8").strip():
        errors.append(f"{pkg}: mock coverage missing entries: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-root", default="delivery")
    parser.add_argument("--enforce-batch-distribution", action="store_true")
    args = parser.parse_args()

    root = Path(args.delivery_root)
    errors: list[str] = []
    checked = 0
    rounds_by_section: dict[str, list[int]] = {}
    for batch in sorted(root.glob("*/batch*.jsonl")):
        pkg = batch.parent
        check_package_metadata(pkg, errors)
        for obj in load_jsonl(batch):
            checked += 1
            section = (obj.get("meta") or {}).get("section", pkg.name.split("_", 1)[0])
            check_meta(pkg, obj, errors)
            check_jsonl_text(pkg, obj, errors)
            rounds = check_rounds(pkg, obj, errors)
            rounds_by_section.setdefault(section, []).append(rounds)
            check_verifier(pkg, obj, errors)
        check_mock(pkg, errors)

    if args.enforce_batch_distribution:
        for section, rounds in sorted(rounds_by_section.items()):
            if not rounds:
                continue
            avg = sum(rounds) / len(rounds)
            if avg < 7:
                errors.append(f"section {section}: avg_tool_rounds={avg:.2f} < 7")
            if len(rounds) >= 20:
                total = len(rounds)
                counts = {bucket: 0 for bucket in ("4-6", "7-10", "11+")}
                for value in rounds:
                    bucket = round_bucket(value)
                    if bucket in counts:
                        counts[bucket] += 1
                low = {
                    bucket: round(count / total, 3)
                    for bucket, count in counts.items()
                    if count / total < 0.15
                }
                if low:
                    errors.append(f"section {section}: round bucket ratios below 15% {low}")
            else:
                print(
                    f"[delivery-quality] section {section}: distribution gate skipped "
                    f"for sample_count={len(rounds)} (<20); rounds={rounds}"
                )

    if errors:
        print(f"[delivery-quality] checked={checked} failed={len(errors)}")
        for err in errors:
            print(f"ERROR: {err}")
        return 1
    print(f"[delivery-quality] checked={checked} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
