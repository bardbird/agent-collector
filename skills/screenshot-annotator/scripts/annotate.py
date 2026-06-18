"""Draw numbered callouts on screenshots."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_box(value: str):
    parts = value.split(",", 5)
    if len(parts) != 6:
        raise argparse.ArgumentTypeError("box must be x1,y1,x2,y2,index,label")
    x1, y1, x2, y2 = [int(v) for v in parts[:4]]
    return x1, y1, x2, y2, parts[4], parts[5]


def load_font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--box", action="append", type=parse_box, required=True)
    args = parser.parse_args()

    image = Image.open(args.inp).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = load_font(max(16, image.height // 36))
    label_font = load_font(max(12, image.height // 54))

    for x1, y1, x2, y2, idx, label in args.box:
        color = (214, 48, 49)
        draw.rectangle((x1, y1, x2, y2), outline=color, width=max(3, image.width // 300))
        badge = f"{idx}"
        bbox = draw.textbbox((0, 0), badge, font=font)
        bw, bh = bbox[2] - bbox[0] + 12, bbox[3] - bbox[1] + 8
        bx, by = x1, max(0, y1 - bh - 4)
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=4, fill=color)
        draw.text((bx + 6, by + 4), badge, fill=(255, 255, 255), font=font)
        if label:
            draw.text((bx + bw + 6, by + 5), label[:40], fill=color, font=label_font)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    image.save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
