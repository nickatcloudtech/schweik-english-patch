#!/usr/bin/env python3
"""Export UI button/cursor crops for text translation (menu labels are baked into QDA art)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qda_tools import decode_rle_frame, parse_qda

DEFAULT_UI = ROOT / "patch" / "ui_src" / "Resource"
DEFAULT_OUT = ROOT / "translation" / "ui_text"
DEFAULT_CSV = ROOT / "translation" / "ui_strings.csv"

FILENAME_HINTS = {
    "new_active": "New Game (active)",
    "new_selected": "New Game (selected)",
    "new_pressed": "New Game (pressed)",
    "load_active": "Load (active)",
    "load_selected": "Load (selected)",
    "load_pressed": "Load (pressed)",
    "save_active": "Save (active)",
    "save_selected": "Save (selected)",
    "save_pressed": "Save (pressed)",
    "resume_active": "Resume (active)",
    "resume_selected": "Resume (selected)",
    "resume_pressed": "Resume (pressed)",
    "exit_active": "Exit (active)",
    "exit_selected": "Exit (selected)",
    "exit_pressed": "Exit (pressed)",
    "music": "Music toggle",
    "zvuk": "Sound toggle",
    "to main normal": "To Main Menu (normal)",
    "to main select": "To Main Menu (selected)",
    "to main pressed": "To Main Menu (pressed)",
    "to main active": "To Main Menu (active)",
    "yes active": "Yes (active)",
    "yes select": "Yes (selected)",
    "yes pressed": "Yes (pressed)",
    "yes selected": "Yes (selected)",
    "no active": "No (active)",
    "no selected": "No (selected)",
    "no pressed": "No (pressed)",
    "main menu": "Main Menu",
    "main menu_activ": "Main Menu (active)",
    "main menu_press": "Main Menu (pressed)",
    "кнопка меню": "In-game menu button",
    "кнопка меню активно": "In-game menu button (active)",
    "restart": "Restart",
    "restart selected": "Restart (selected)",
    "прокрутка лево": "Inventory scroll left",
    "прокрутка право": "Inventory scroll right",
}


def english_hint(path: Path) -> str:
    stem = path.stem.lower()
    for key, hint in FILENAME_HINTS.items():
        if key in stem:
            return hint
    if "курсор" in stem:
        return "Mouse cursor (graphic only — no text expected)"
    return ""


def visible_bbox(image):
    px = image.convert("RGBA").load()
    width, height = image.size
    min_x, min_y = width, height
    max_x, max_y = -1, -1
    for y in range(height):
        for x in range(width):
            if px[x, y][3]:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        return None
    return min_x, min_y, max_x + 1, max_y + 1


def ollama_vision(image_path: Path, *, model: str, endpoint: str) -> str:
    payload = {
        "model": model,
        "prompt": (
            "This image is a button or UI label from a Russian adventure game. "
            "Return ONLY the visible Russian text, or NONE if there is no text "
            "(e.g. icons/cursors). No explanation."
        ),
        "images": [__import__("base64").b64encode(image_path.read_bytes()).decode("ascii")],
        "stream": False,
        "think": False,
    }
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    text = (body.get("response") or "").strip()
    if text.upper() == "NONE":
        return ""
    return text


def collect_qda_files(source: Path) -> list[Path]:
    return sorted(source.rglob("*.qda"))


def export_rows(
    source: Path,
    output_dir: Path,
    *,
    vision: bool,
    model: str,
    endpoint: str,
) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for qda_path in collect_qda_files(source):
        rel = qda_path.relative_to(source)
        animation = parse_qda(qda_path.read_bytes())
        for index, frame in enumerate(animation.frames):
            image = decode_rle_frame(frame)
            bbox = visible_bbox(image)
            if not bbox:
                continue
            crop = image.crop(bbox)
            frame_suffix = f"_f{index:02d}" if len(animation.frames) > 1 else ""
            crop_name = f"{rel.as_posix().replace('/', '__')}{frame_suffix}.png"
            crop_path = output_dir / crop_name
            crop.save(crop_path)

            row = {
                "id": f"{rel.as_posix()}{frame_suffix}",
                "source_qda": str(rel),
                "frame": str(index),
                "english_hint": english_hint(qda_path),
                "crop_png": str(crop_path.relative_to(output_dir.parent.parent)),
                "russian_text": "",
                "english_text": "",
                "notes": "Text is baked into pixels; translate english_text then repaint in GIMP.",
            }
            if vision and english_hint(qda_path) != "Mouse cursor (graphic only — no text expected)":
                try:
                    row["russian_text"] = ollama_vision(crop_path, model=model, endpoint=endpoint)
                except Exception as exc:  # noqa: BLE001 - report and continue
                    row["notes"] = f"Vision OCR failed: {exc}"
            rows.append(row)

    return rows


def write_csv(rows: list[dict[str, str]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "source_qda",
        "frame",
        "english_hint",
        "crop_png",
        "russian_text",
        "english_text",
        "notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_UI)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--vision",
        action="store_true",
        help="Use local Ollama vision model to read Russian text from crops",
    )
    parser.add_argument("--model", default="llava")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    rows = export_rows(
        args.source,
        args.output,
        vision=args.vision,
        model=args.model,
        endpoint=args.endpoint,
    )
    write_csv(rows, args.csv)
    print(f"Exported {len(rows)} UI crop(s) to {args.output}")
    print(f"CSV: {args.csv}")
    print("Fill english_text, repaint matching PNGs in patch/qda_work, then: python3 tools/qda_edit.py import")


if __name__ == "__main__":
    main()