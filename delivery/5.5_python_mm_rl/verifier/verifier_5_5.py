"""§5.5 multimodal Python FC RL verifier.

Standard interface:
    verify(pred: str, answer_gt: str, model_query: str) -> dict

Security rule: output paths must be extracted from pred only. answer_gt and
model_query describe expected conditions, but must not be trusted as the model's
claimed output path; otherwise a pre-existing artifact would make the verifier
constant-true for empty or irrelevant predictions.
"""
from __future__ import annotations

import json
import re
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def _item_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    root = _item_root()
    if root.name == "5.5_python_mm_rl" and root.parent.name == "delivery":
        return root.parent.parent
    return root


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _load_config(answer_gt: str, model_query: str, pred: str) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    for text in (answer_gt, model_query):
        try:
            parsed = json.loads(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            cfg.update(parsed)

    joined = "\n".join([answer_gt or "", model_query or "", pred or ""])
    if "expected_size" not in cfg:
        m = re.search(r"(\d{2,5})\s*[x×]\s*(\d{2,5})", joined)
        if m:
            cfg["expected_size"] = [int(m.group(1)), int(m.group(2))]

    checks = set(cfg.get("checks") or [])
    lowered = joined.lower()
    if "red" in lowered and ("corner" in lowered or "角标" in joined) and "rework" in lowered:
        checks.add("red_corner_badge")
    if checks:
        cfg["checks"] = sorted(checks)
    return cfg


def _candidate_paths(pred: str, cfg: Dict[str, Any]) -> Iterable[Path]:
    root = _item_root()
    repo = _repo_root()
    seen: set[Path] = set()
    raw_paths = re.findall(r"[\w./-]+\.(?:png|jpg|jpeg|webp)", pred or "", flags=re.I)

    for raw in raw_paths:
        candidates = []
        if raw.startswith("delivery/5.5_python_mm_rl/"):
            candidates.append(repo / raw)
        else:
            candidates.append(root / raw)
        rel = raw.replace("out/tool_outputs/", "assets/outputs/")
        rel = rel.replace("delivery/5.5_python_mm_rl/", "")
        candidates.append(root / rel)
        if root.name != "5.5_python_mm_rl":
            candidates.append(root / "delivery/5.5_python_mm_rl" / rel)
        for p in candidates:
            if p not in seen:
                seen.add(p)
                yield p


def _png_rows(path: Path) -> Tuple[int, int, list[bytes]]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")

    pos = 8
    width = height = color_type = bit_depth = None
    compressed = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None:
        raise ValueError("missing IHDR")
    if bit_depth != 8 or color_type not in (2, 6):
        raise ValueError(f"unsupported PNG format bit_depth={bit_depth} color_type={color_type}")

    channels = 3 if color_type == 2 else 4
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    rows = []
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        filt = raw[i]
        i += 1
        cur = bytearray(raw[i:i + stride])
        i += stride
        recon = bytearray(stride)
        for x, val in enumerate(cur):
            left = recon[x - channels] if x >= channels else 0
            up = prev[x]
            up_left = prev[x - channels] if x >= channels else 0
            if filt == 0:
                out = val
            elif filt == 1:
                out = (val + left) & 0xFF
            elif filt == 2:
                out = (val + up) & 0xFF
            elif filt == 3:
                out = (val + ((left + up) // 2)) & 0xFF
            elif filt == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                pr = left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                out = (val + pr) & 0xFF
            else:
                raise ValueError(f"unsupported PNG filter {filt}")
            recon[x] = out
        rows.append(bytes(recon))
        prev = recon
    return width, height, rows


def _corner_ratios(width: int, height: int, rows: list[bytes]) -> Tuple[float, float]:
    channels = len(rows[0]) // width
    x0 = max(0, width - 260)
    y1 = min(height, 220)
    total = red = light = 0
    for y in range(y1):
        row = rows[y]
        for x in range(x0, width):
            off = x * channels
            r, g, b = row[off], row[off + 1], row[off + 2]
            total += 1
            if r > 180 and g < 90 and b < 90:
                red += 1
            if r > 215 and g > 215 and b > 215:
                light += 1
    denom = max(1, total)
    return red / denom, light / denom


def _verify_path(path: Path, cfg: Dict[str, Any]) -> Tuple[bool, str]:
    width, height, rows = _png_rows(path)
    expected_size = cfg.get("expected_size")
    if expected_size and (width, height) != tuple(expected_size):
        return False, f"size mismatch: {(width, height)} != {tuple(expected_size)}"

    checks = set(cfg.get("checks") or [])
    if "red_corner_badge" in checks:
        red_ratio, light_ratio = _corner_ratios(width, height, rows)
        if red_ratio < float(cfg.get("red_ratio_min", 0.16)):
            return False, f"red corner badge ratio too low: {red_ratio:.3f}"
        if light_ratio < float(cfg.get("light_text_ratio_min", 0.002)):
            return False, f"light text ratio too low: {light_ratio:.3f}"
        return True, f"image ok; red badge ratio={red_ratio:.3f}; light text ratio={light_ratio:.3f}"

    return True, f"image exists; size={(width, height)}"


def verify(pred: str, answer_gt: str, model_query: str = "") -> Dict:
    cfg = _load_config(answer_gt, model_query, pred)
    last_error: Optional[str] = None
    checked = False
    for path in _candidate_paths(pred, cfg):
        checked = True
        if not path.exists():
            last_error = f"missing output image: {path}"
            continue
        try:
            ok, reason = _verify_path(path, cfg)
        except Exception as exc:
            ok, reason = False, f"{path}: {exc}"
        if ok:
            return {"pass": True, "score": 1.0, "reason": reason}
        last_error = reason

    reason = last_error if checked else "no output image path found in pred"
    return {"pass": False, "score": 0.0, "reason": reason}


if __name__ == "__main__":
    sample_pred = "输出文件：out/tool_outputs/device_label_rework_5_5_formal.png，尺寸 960 x 620，REWORK red badge"
    print(verify(sample_pred, "output image exists, original size 960x620 is preserved, and a red REWORK corner badge is present", ""))
