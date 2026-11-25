#!/usr/bin/env python3
"""Extract the in-game Prague map (Resource/Карта) for English UI work.

The map scene (``1Карта``) uses:
  - ``Static/fon.tga`` — parchment city plan background (German title in retail art)
  - ``Animation/*.qda`` — click/highlight zones + a few text label sprites

Most location QDAs are 800×600 mostly-transparent overlays (do not repaint these).
Only the 209×62 label sprites contain Russian typography that must be translated.
"""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pak_paths import decode_pak_path
from tools.qda_tools import parse_qda, qda_to_png
from tools.tga_convert import ensure_engine_tga

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_UI_SRC = ROOT / "patch" / "ui_src" / "Resource" / "Карта"
DEFAULT_WORK = ROOT / "patch" / "qda_work" / "Карта"
DEFAULT_CSV = ROOT / "translation" / "map_strings.csv"

MAP_PREFIX = "Resource\\Карта\\"

LABEL_MAX_WIDTH = 300

LOCATION_HINTS = {
    "вокзал": "Train station (click zone only — no baked label art)",
    "площадь": "Square (click zone only)",
    "психушка": "Asylum (click zone only)",
    "парк": "Park (click zone only)",
    "храм": "Temple (click zone only)",
    "дом каца": "Katz's house (click zone only)",
    "квартира лукаша": "Lukash's apartment (click zone only)",
    "участок и комиссариат": "Police station & commissariat (click zone only)",
    "трактир": 'Tavern "At the Cup" — translate label sprite',
    "кухня швейка": "Schweik's kitchen — translate label sprite",
}

ENGLISH_SUGGESTIONS = {
    "трактир": 'Tavern "At the Cup"',
    "трактир_подсветка": 'Tavern "At the Cup" (highlight)',
    "кухня швейка": "Schweik's Kitchen",
    "кухня швейка_подсветка": "Schweik's Kitchen (highlight)",
    "fon.tga": "City Map of Prague (optional — retail art uses German title)",
}


def is_map_path(path: str) -> bool:
    return path.startswith(MAP_PREFIX)


def classify_qda(filename: str, width: int, height: int) -> str:
    stem = Path(filename).stem.replace("_подсветка", "")
    if width <= LABEL_MAX_WIDTH:
        return "label_sprite"
    return "click_zone_overlay"


def extract_map_files(pak_path: Path, ui_src: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            path = decode_pak_path(raw_name)
            if not is_map_path(path):
                continue
            rel = path[len(MAP_PREFIX) :].replace("\\", "/")
            target = ui_src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(raw_name)
            target.write_bytes(data)

            row = {
                "archive_path": path,
                "local_path": str(target.relative_to(ui_src.parent.parent)),
                "filename": Path(rel).name,
                "kind": "background" if rel.endswith(".tga") else "unknown",
                "width": "",
                "height": "",
                "translate": "optional",
                "english_hint": ENGLISH_SUGGESTIONS.get(Path(rel).name, ""),
                "notes": "",
            }
            if rel.endswith(".qda"):
                frame = parse_qda(data).frames[0]
                kind = classify_qda(rel, frame.canvas_w, frame.canvas_h)
                row.update(
                    {
                        "kind": kind,
                        "width": str(frame.canvas_w),
                        "height": str(frame.canvas_h),
                        "translate": "yes" if kind == "label_sprite" else "no",
                        "notes": LOCATION_HINTS.get(
                            Path(rel).stem.replace("_подсветка", ""),
                            "Transparent click/highlight mask — keep geometry, do not add text",
                        ),
                    }
                )
                if not row["english_hint"]:
                    row["english_hint"] = row["notes"]
            elif rel.endswith(".tga"):
                row["notes"] = "Parchment map artwork; location markers are colored blocks, not text labels"
            rows.append(row)
    return rows


def export_work_pngs(
    ui_src: Path,
    work_dir: Path,
    *,
    export_all_animations: bool = False,
    keep_work_static: bool = False,
) -> int:
    count = 0
    for qda_path in sorted((ui_src / "Animation").glob("*.qda")):
        frame = parse_qda(qda_path.read_bytes()).frames[0]
        kind = classify_qda(qda_path.name, frame.canvas_w, frame.canvas_h)
        if not export_all_animations and kind != "label_sprite":
            continue
        if export_all_animations and kind == "click_zone_overlay":
            png_path = work_dir / "Animation" / "zones" / f"{qda_path.stem}.png"
        else:
            png_path = work_dir / "Animation" / f"{qda_path.stem}.png"
        png_path.parent.mkdir(parents=True, exist_ok=True)
        qda_to_png(qda_path.read_bytes(), png_path)
        count += 1
        print(f"export {png_path.relative_to(work_dir)}")

    fon = ui_src / "Static" / "fon.tga"
    work_fon = work_dir / "Static" / "fon.png"
    if keep_work_static and work_fon.exists():
        print(f"keep {work_fon.relative_to(work_dir)} (custom map background)")
    elif fon.exists():
        from io import BytesIO

        from PIL import Image

        converted = ensure_engine_tga(fon.read_bytes(), fon)
        work_fon.parent.mkdir(parents=True, exist_ok=True)
        Image.open(BytesIO(converted)).save(work_fon)
        count += 1
        print(f"export {work_fon.relative_to(work_dir)}")
    return count


def clear_map_overrides(overrides_root: Path) -> int:
    """Remove packed map QDAs from patch/overrides (keep Static if caller wants)."""
    animation_dir = overrides_root / "Карта" / "Animation"
    if not animation_dir.exists():
        return 0
    removed = 0
    for path in animation_dir.glob("*.qda"):
        path.unlink()
        removed += 1
    return removed


def write_csv(rows: list[dict[str, str]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "archive_path",
        "local_path",
        "filename",
        "kind",
        "width",
        "height",
        "translate",
        "english_hint",
        "notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["archive_path"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--ui-src", type=Path, default=DEFAULT_UI_SRC)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--no-png", action="store_true", help="Skip PNG export for GIMP")
    parser.add_argument(
        "--export-all-animations",
        action="store_true",
        help="Export every Animation/*.qda as PNG (zones go under Animation/zones/)",
    )
    parser.add_argument(
        "--keep-work-static",
        action="store_true",
        help="Do not overwrite patch/qda_work/Карта/Static/fon.png",
    )
    parser.add_argument(
        "--reset-overrides",
        action="store_true",
        help="Delete patch/overrides/Resource/Карта/Animation/*.qda (start label edit over)",
    )
    args = parser.parse_args()

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    rows = extract_map_files(pak, args.ui_src)
    write_csv(rows, args.csv)
    print(f"Extracted {len(rows)} map file(s) to {args.ui_src}")
    print(f"Inventory: {args.csv}")

    labels = sum(1 for row in rows if row["translate"] == "yes")
    zones = sum(1 for row in rows if row["kind"] == "click_zone_overlay")
    print(f"  {labels} label sprite(s) to translate, {zones} click-zone overlay(s) (geometry only)")

    overrides_root = ROOT / "patch" / "overrides" / "Resource"
    if args.reset_overrides:
        removed = clear_map_overrides(overrides_root)
        print(f"Cleared {removed} override QDA(s) from {overrides_root / 'Карта' / 'Animation'}")

    if not args.no_png:
        exported = export_work_pngs(
            args.ui_src,
            args.work,
            export_all_animations=args.export_all_animations,
            keep_work_static=args.keep_work_static,
        )
        print(f"Exported {exported} PNG(s) for editing to {args.work}")


if __name__ == "__main__":
    main()