"""Generate local input assets for real §5.1-§5.9 capture runs.

This script does not generate delivery JSONL. Send-to-review JSONL must come
from proxy-captured raw_turns plus the section transformers.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
INPUTS = ASSETS / "inputs"
DATA = ASSETS / "data"
OUTPUTS = ASSETS / "outputs"
TASKS = ROOT / "tasks"


def font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def reset_dirs() -> None:
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    for path in (INPUTS, DATA, OUTPUTS, TASKS):
        path.mkdir(parents=True, exist_ok=True)


def draw_portrait_hero() -> None:
    img = Image.new("RGB", (900, 620), (238, 241, 246))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 900, 620), fill=(235, 239, 245))
    draw.rectangle((500, 60, 840, 560), fill=(40, 74, 116))
    draw.ellipse((120, 115, 360, 355), fill=(229, 178, 141), outline=(115, 83, 62), width=5)
    draw.rectangle((175, 350, 410, 590), fill=(41, 96, 180))
    draw.ellipse((190, 195, 220, 225), fill=(30, 35, 45))
    draw.ellipse((280, 195, 310, 225), fill=(30, 35, 45))
    draw.arc((215, 240, 300, 305), 10, 170, fill=(95, 48, 48), width=4)
    draw.rounded_rectangle((555, 140, 805, 235), radius=18, fill=(255, 255, 255))
    draw.text((585, 168), "PRO BADGE", fill=(40, 74, 116), font=font(30))
    draw.text((560, 400), "Launch visual", fill=(255, 255, 255), font=font(34))
    img.save(INPUTS / "portrait_hero.png")


def draw_training_console() -> None:
    ui = Image.new("RGB", (1024, 640), (247, 248, 250))
    draw = ImageDraw.Draw(ui)
    draw.rectangle((0, 0, 1024, 72), fill=(28, 38, 58))
    draw.text((32, 22), "Training Console", fill=(255, 255, 255), font=font(26))
    draw.rounded_rectangle((38, 112, 350, 570), radius=8, outline=(210, 216, 228), width=2, fill=(255, 255, 255))
    draw.text((64, 140), "Dataset Import", fill=(28, 38, 58), font=font(24))
    draw.rounded_rectangle((430, 112, 960, 238), radius=8, outline=(210, 216, 228), width=2, fill=(255, 255, 255))
    draw.text((462, 142), "Validation failed: 17 rows missing labels", fill=(185, 54, 42), font=font(24))
    draw.rounded_rectangle((430, 280, 960, 570), radius=8, outline=(210, 216, 228), width=2, fill=(255, 255, 255))
    draw.text((462, 320), "Next action", fill=(28, 38, 58), font=font(24))
    draw.rounded_rectangle((462, 382, 650, 438), radius=6, fill=(38, 102, 204))
    draw.text((492, 398), "Fix Labels", fill=(255, 255, 255), font=font(22))
    ui.save(INPUTS / "training_console.png")


def draw_event_venue() -> None:
    venue = Image.new("RGB", (960, 600), (218, 230, 242))
    draw = ImageDraw.Draw(venue)
    draw.rectangle((0, 360, 960, 600), fill=(92, 145, 108))
    draw.rectangle((90, 220, 420, 430), fill=(170, 118, 78))
    draw.polygon([(60, 220), (255, 110), (450, 220)], fill=(135, 75, 62))
    draw.rectangle((555, 205, 860, 430), fill=(230, 232, 236))
    draw.text((600, 286), "Indoor Hall", fill=(62, 72, 88), font=font(36))
    draw.text((105, 292), "Outdoor Lawn", fill=(255, 255, 255), font=font(34))
    venue.save(INPUTS / "event_venue.png")


def draw_apollo_exhibit_card() -> None:
    img = Image.new("RGB", (1180, 760), (232, 229, 222))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1180, 760), fill=(232, 229, 222))
    draw.rectangle((0, 0, 1180, 92), fill=(23, 32, 43))
    draw.text((42, 28), "DESTINATION MOON", fill=(246, 246, 242), font=font(34))

    draw.rectangle((80, 150, 690, 610), fill=(35, 40, 47))
    draw.polygon(
        [(230, 205), (540, 205), (645, 475), (475, 590), (265, 575), (145, 455)],
        fill=(145, 129, 105),
        outline=(228, 216, 188),
    )
    draw.polygon(
        [(282, 238), (500, 235), (574, 440), (462, 520), (310, 510), (225, 422)],
        fill=(86, 91, 93),
        outline=(210, 210, 204),
    )
    draw.ellipse((328, 310, 470, 450), fill=(22, 27, 32), outline=(205, 210, 208), width=5)
    draw.line((145, 455, 80, 610), fill=(222, 212, 186), width=4)
    draw.line((645, 475, 690, 610), fill=(222, 212, 186), width=4)

    draw.rectangle((755, 148, 1085, 610), fill=(248, 248, 244), outline=(164, 157, 145), width=3)
    draw.text((790, 184), "APOLLO 11", fill=(24, 33, 43), font=font(38))
    draw.text((790, 236), "COMMAND MODULE", fill=(24, 33, 43), font=font(31))
    draw.text((790, 290), "COLUMBIA", fill=(130, 60, 45), font=font(44))
    draw.line((790, 352, 1050, 352), fill=(188, 181, 170), width=2)
    draw.text((790, 382), "CM-107", fill=(28, 36, 45), font=font(32))
    draw.text((790, 430), "Crew: Armstrong", fill=(28, 36, 45), font=font(24))
    draw.text((790, 466), "Aldrin, Collins", fill=(28, 36, 45), font=font(24))
    draw.text((790, 520), "Catalog: A19700102000", fill=(78, 82, 86), font=font(22))
    draw.text((96, 660), "Generated exhibit reference for search-capture testing", fill=(82, 78, 72), font=font(22))
    img.save(INPUTS / "apollo_columbia_exhibit_001.png")


def draw_zarya_module_card() -> None:
    img = Image.new("RGB", (1180, 760), (226, 232, 236))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1180, 760), fill=(226, 232, 236))
    draw.rectangle((0, 0, 1180, 96), fill=(18, 43, 65))
    draw.text((40, 28), "ORBITAL OUTPOST ARCHIVE", fill=(246, 248, 250), font=font(34))

    draw.rectangle((70, 145, 710, 610), fill=(12, 24, 35))
    draw.ellipse((110, 170, 660, 590), outline=(68, 98, 126), width=2)
    draw.line((110, 380, 660, 380), fill=(68, 98, 126), width=2)
    draw.line((385, 170, 385, 590), fill=(68, 98, 126), width=2)
    draw.rectangle((240, 310, 555, 450), fill=(184, 194, 199), outline=(238, 242, 244), width=4)
    draw.rectangle((145, 335, 240, 425), fill=(126, 141, 150), outline=(238, 242, 244), width=3)
    draw.rectangle((555, 335, 645, 425), fill=(126, 141, 150), outline=(238, 242, 244), width=3)
    draw.rectangle((300, 285, 500, 310), fill=(95, 112, 126))
    draw.rectangle((302, 450, 498, 476), fill=(95, 112, 126))
    draw.text((272, 352), "FGB", fill=(20, 35, 45), font=font(32))
    draw.text((352, 352), "ZARYA", fill=(20, 35, 45), font=font(32))

    draw.rectangle((760, 145, 1088, 610), fill=(250, 250, 247), outline=(137, 145, 150), width=3)
    draw.text((792, 182), "ZARYA", fill=(18, 43, 65), font=font(50))
    draw.text((792, 244), "Functional Cargo Block", fill=(18, 43, 65), font=font(26))
    draw.line((792, 292, 1054, 292), fill=(178, 184, 188), width=2)
    draw.text((792, 324), "First ISS module", fill=(93, 54, 45), font=font(30))
    draw.text((792, 374), "Also called: FGB", fill=(34, 46, 58), font=font(24))
    draw.text((792, 420), "Role: early power", fill=(34, 46, 58), font=font(24))
    draw.text((792, 454), "propulsion & guidance", fill=(34, 46, 58), font=font(24))
    draw.text((792, 520), "Archive ref: ISS-RS-01", fill=(84, 90, 96), font=font(22))
    draw.text((96, 664), "Generated reference panel for multimodal search RL testing", fill=(78, 86, 92), font=font(22))
    img.save(INPUTS / "zarya_module_panel_001.png")


def write_data_files() -> None:
    (DATA / "week_notes.md").write_text(
        "- Normalized 18 partner data feeds\n"
        "- Data-cleaning validation reached 100% pass rate\n"
        "- Shipped dashboard ingestion monitor\n"
        "- Risk: partner C still sends late files\n",
        encoding="utf-8",
    )
    (DATA / "sales_q1.csv").write_text(
        "date,region,revenue\n"
        "2026-01-12,NA,412300.25\n"
        "2026-02-18,EU,386700.50\n"
        "2026-03-22,APAC,485350.00\n"
        "2026-04-03,NA,101200.00\n",
        encoding="utf-8",
    )
    (DATA / "incidents.jsonl").write_text(
        '{"date":"2026-05-03","severity":"P0","service":"checkout"}\n'
        '{"date":"2026-05-09","severity":"P2","service":"search"}\n'
        '{"date":"2026-05-18","severity":"P1","service":"checkout"}\n'
        '{"date":"2026-05-29","severity":"P1","service":"billing"}\n',
        encoding="utf-8",
    )


def write_tasks() -> None:
    (TASKS / "capture_tasks.md").write_text(
        "# §5.1-§5.9 真实采集任务种子\n\n"
        "送检 JSONL 必须来自 `out/raw_turns/*.json` 的真实代理采集和转换。以下只提供输入素材和目标导向 query。\n\n"
        "## 5.1 Skills SFT\n"
        "- The launch avatar has to come from `samples/assets/inputs/portrait_hero.png`. The face cannot feel chopped off, and the product badge should still be visible enough for the sales deck.\n"
        "- This training screenshot at `samples/assets/inputs/training_console.png` is confusing for new operators. Mark the areas they should notice first and keep the legend short.\n\n"
        "## 5.2 Skills RL\n"
        "- My raw week notes are in `samples/assets/data/week_notes.md`. I need a manager-ready weekly update, and the data-cleaning work should stand on its own.\n\n"
        "## 5.3 RL QA Sandbox\n"
        "- The finance slide image is only for context; the CSV at `samples/assets/data/sales_q1.csv` is the source of truth. What is Q1 revenue for the CFO, rounded to two decimals?\n\n"
        "## 5.4 Multimodal Python SFT\n"
        "- This venue graphic at `samples/assets/inputs/event_venue.png` needs to fit a portrait invite and carry a small INTERNAL watermark. Make it clean enough that the outdoor and indoor options remain readable.\n\n"
        "## 5.5 Multimodal Python RL\n"
        "- I need the exact center square from `samples/assets/inputs/portrait_hero.png` for an automated avatar test. The result has to be 512 by 512.\n\n"
        "## 5.6 Multimodal Search SFT\n"
        "- The museum-card image at `samples/assets/inputs/apollo_columbia_exhibit_001.png` is for a science post. Identify the exhibit and give a tight, citable caption about its Apollo 11 role and current display context.\n\n"
        "## 5.7 Multimodal Search RL\n"
        "- The station-module panel at `samples/assets/inputs/zarya_module_panel_001.png` is for an ISS timeline card. What exact launch date, launch vehicle, and launch site should be used?\n\n"
        "## 5.8 Tool Generalization SFT\n"
        "- Friday's Shanghai client demo cannot get rained out. Use the venue options in `samples/assets/inputs/event_venue.png` and make the practical arrangement.\n\n"
        "## 5.9 Tool Generalization RL\n"
        "- I need the cheapest in-stock AirPods Pro 3 option deliverable to Shanghai this week. Give me the final payable price, not the sticker price.\n",
        encoding="utf-8",
    )


def main() -> None:
    reset_dirs()
    draw_portrait_hero()
    draw_training_console()
    draw_event_venue()
    draw_apollo_exhibit_card()
    draw_zarya_module_card()
    write_data_files()
    write_tasks()
    print(f"[inputs] wrote generated images to {INPUTS}")
    print(f"[inputs] wrote data files to {DATA}")
    print(f"[inputs] wrote task seeds to {TASKS / 'capture_tasks.md'}")


if __name__ == "__main__":
    main()
