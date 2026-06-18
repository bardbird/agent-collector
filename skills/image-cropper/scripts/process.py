"""image-cropper 处理脚本。

依赖: Pillow >= 9.0
用法:
  python process.py --op crop      --in IN --out OUT --size 512x512
  python process.py --op rotate    --in IN --out OUT --angle -90
  python process.py --op scale     --in IN --out OUT --size 800x600
  python process.py --op watermark --in IN --out OUT --text SAMPLE --position bottom-right
  python process.py --op filter    --in IN --out OUT --kind grayscale
"""
from __future__ import annotations
import argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as e:
    raise SystemExit("Pillow not installed; pip install Pillow") from e


def parse_size(s: str):
    w, h = s.lower().split("x")
    return int(w), int(h)


def crop_center(img, size):
    w, h = img.size
    tw, th = size
    left, top = (w - tw) // 2, (h - th) // 2
    return img.crop((left, top, left + tw, top + th))


def add_watermark(img, text, position):
    img = img.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Helvetica.ttc", max(20, img.size[1] // 25))
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = img.size
    pos = {
        "bottom-right": (w - tw - 20, h - th - 20),
        "top-left": (20, 20),
        "center": ((w - tw) // 2, (h - th) // 2),
    }.get(position, (w - tw - 20, h - th - 20))
    draw.text(pos, text, fill=(255, 255, 255, 200), font=font)
    return Image.alpha_composite(img, layer).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--op", required=True,
                    choices=["crop", "rotate", "scale", "watermark", "filter"])
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", help="WxH (crop/scale)")
    ap.add_argument("--angle", type=float, help="degrees (rotate, negative=CW)")
    ap.add_argument("--text", help="watermark text")
    ap.add_argument("--position", default="bottom-right",
                    choices=["bottom-right", "top-left", "center"])
    ap.add_argument("--kind", default="grayscale",
                    choices=["grayscale", "invert"])
    a = ap.parse_args()

    img = Image.open(a.inp)
    if a.op == "crop":
        out = crop_center(img, parse_size(a.size))
    elif a.op == "rotate":
        out = img.rotate(a.angle or 0, expand=True)
    elif a.op == "scale":
        out = img.resize(parse_size(a.size))
    elif a.op == "watermark":
        out = add_watermark(img, a.text or "SAMPLE", a.position)
    elif a.op == "filter":
        out = ImageOps.grayscale(img) if a.kind == "grayscale" else ImageOps.invert(img.convert("RGB"))
    else:
        raise SystemExit(f"unknown op {a.op}")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)
    print(f"[image-cropper] op={a.op} -> {a.out} size={out.size}")


if __name__ == "__main__":
    main()
