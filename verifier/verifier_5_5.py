"""§5.5 多模态 Python FC 强化 — verifier(脚本式)。

§5.5 迷你样例采用脚本验证:核验输出图片的尺寸 / 中心裁剪 / 文件存在等。
本骨架按 verifier_type=script 实现,接受额外 kwargs 描述期望参数。
"""
from __future__ import annotations
import os
from typing import Dict, Optional, Tuple


def _try_pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


def verify(pred: str, answer_gt: str, model_query: str = "",
           pred_path: Optional[str] = None,
           input_path: Optional[str] = None,
           expected_size: Optional[Tuple[int, int]] = None,
           op: str = "crop_center") -> Dict:
    Image = _try_pil()
    if Image is None:
        return {"pass": False, "score": 0.0,
                "reason": "Pillow not installed; pip install Pillow"}
    if not pred_path or not os.path.exists(pred_path):
        return {"pass": False, "score": 0.0,
                "reason": f"pred_path missing: {pred_path!r}"}

    img = Image.open(pred_path)
    if expected_size and img.size != tuple(expected_size):
        return {"pass": False, "score": 0.0,
                "reason": f"size mismatch: {img.size} != {expected_size}"}

    if op == "crop_center" and input_path and os.path.exists(input_path):
        orig = Image.open(input_path)
        ow, oh = orig.size
        tw, th = (expected_size or img.size)
        left, top = (ow - tw) // 2, (oh - th) // 2
        expected = orig.crop((left, top, left + tw, top + th))
        if list(img.getdata()) == list(expected.getdata()):
            return {"pass": True, "score": 1.0, "reason": "exact center-crop"}
        return {"pass": False, "score": 0.0, "reason": "pixel diff"}

    if op == "red_corner_badge":
        w, h = img.size
        region = img.crop((max(0, w - 260), 0, w, min(h, 160)))
        pixels = list(region.getdata())
        redish = sum(1 for r, g, b, *rest in pixels if r > 180 and g < 90 and b < 90)
        ratio = redish / max(1, len(pixels))
        if ratio >= 0.20:
            return {"pass": True, "score": 1.0,
                    "reason": f"red corner badge detected ratio={ratio:.3f}"}
        return {"pass": False, "score": 0.0,
                "reason": f"red corner badge ratio too low: {ratio:.3f}"}

    # 仅尺寸校验通过 = 弱通过
    return {"pass": True, "score": 0.5,
            "reason": "size ok; deeper verification skipped (no input_path)"}


if __name__ == "__main__":
    print(verify("", "512x512", pred_path="/nonexistent.jpg",
                 expected_size=(512, 512)))
