---
name: screenshot-annotator
description: Annotate screenshots or UI images for training, support, and audit workflows. Use when the user provides an image and asks for key controls, defects, visual regions, or action points to be marked clearly.
---

# screenshot-annotator

Annotate screenshots and UI images with numbered callouts, bounding boxes, and a short legend.

## Workflow

1. Inspect the attached image and identify the objects, controls, or regions that answer the user's goal.
2. Ask a clarifying question only when the intended audience, labels, or severity scale is missing and affects the output.
3. Use `scripts/annotate.py` to draw boxes and numeric labels. Keep labels short and put longer explanations in the legend.
4. Return the output image path, the legend, and any uncertainty that should be reviewed by a human.

## Script

Run:

```bash
python scripts/annotate.py --in INPUT --out OUTPUT --box "120,80,420,170,1,Primary CTA" --box "..."
```

Coordinates are pixel values: `x1,y1,x2,y2,index,label`.

## Quality Rules

- Do not cover the target text with the label.
- Use at most 8 callouts unless the user explicitly asks for a dense audit.
- If the screenshot is too small or blurry, ask for a higher resolution image before annotating.
