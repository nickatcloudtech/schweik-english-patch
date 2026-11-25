#!/usr/bin/env python3
"""Build a master CSV checklist of image assets with baked Russian text.

Scans resource0.pak, classifies readable UI/letter/scene graphics, and tracks
translation progress across the full pipeline:

  pending    — retail Russian only (not extracted, no override)
  extracted  — PNG exists in patch/qda_work/ or patch/letters/png/ (not imported)
  packaged   — override exists but still matches retail (ui_src or pak)
  translated — override differs from retail (English art deployed)

Regenerate after editing PNGs or running qda_edit.py import:
  python3 tools/export_image_checklist.py
"""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.export_ui_text import FILENAME_HINTS, english_hint as ui_english_hint
from tools.extract_letters import (
    classify_asset as classify_letter_asset,
    english_hint as letter_english_hint,
    is_open_door_false_positive,
    normalize_path,
    translate_hint,
)
from tools.extract_map import ENGLISH_SUGGESTIONS, LABEL_MAX_WIDTH, classify_qda as classify_map_qda
from tools.pak_paths import decode_pak_path
from tools.qda_tools import parse_qda

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OVERRIDES = ROOT / "patch" / "overrides"
DEFAULT_UI_SRC = ROOT / "patch" / "ui_src" / "Resource"
DEFAULT_QDA_WORK = ROOT / "patch" / "qda_work"
DEFAULT_LETTERS_PNG = ROOT / "patch" / "letters" / "png"
DEFAULT_OUTPUT = ROOT / "translation" / "image_assets_checklist.csv"

SCENE_READABLE_KEYWORDS = (
    "крупный план",
    "на мыши крупно",
    "газет",
    "листовк",
    "журнал",
    "дневник",
    "доска",
    "розыск",
    "дело пахана",
    "надпис",
    "заставка",
    "final",
    "шкатулка надпись",
    "библи",
    "послание",
    "шифров",
    "письм",
    "конверт",
    "документ",
    "донесен",
    "повестк",
    "открытк",
    "записк",
    "бумажк",
)

MINIGAME_PORTRAIT_STEMS = {
    "готовая картинка",
    "обратная сторона портрета",
    "крупно шифроключ наложен",
}


def normalize_archive_path(path: str) -> str:
    return normalize_path(path)


def resource_relative(path: str) -> str:
    return normalize_archive_path(path).removeprefix("Resource/")


def load_pak_index(pak_path: Path) -> dict[str, bytes]:
    index: dict[str, bytes] = {}
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = normalize_archive_path(decode_pak_path(raw_name))
            index[decoded] = archive.read(raw_name)
    return index


def qda_dimensions(data: bytes) -> tuple[int, int, int]:
    try:
        animation = parse_qda(data)
    except ValueError:
        return 0, 0, 0
    frame = animation.frames[0]
    return frame.canvas_w, frame.canvas_h, len(animation.frames)


def classify_ui(path: str) -> tuple[str, str, str] | None:
    lower = normalize_archive_path(path).lower()
    if lower.startswith("resource/interface/") and lower.endswith(".qda"):
        rel = resource_relative(path)
        hint = ui_english_hint(Path(rel))
        priority = "required"
        if hint == "Mouse cursor (graphic only — no text expected)":
            return None
        if "fon.tga" in lower:
            return None
        return "ui_menu", priority, hint or "Menu / dialog button label"
    if lower.startswith("resource/interface/") and lower.endswith(".tga"):
        if "main menu/fon.tga" in lower:
            return "ui_menu", "optional", "Main menu background (game title art)"
        return "ui_menu", "optional", "UI screen background"
    if lower.startswith("resource/inventory/"):
        rel = Path(resource_relative(path))
        hint = ui_english_hint(rel)
        return "ui_inventory_bar", "required", hint or "Inventory bar UI"
    if lower.startswith("resource/экран смерти/"):
        rel = Path(resource_relative(path))
        hint = ui_english_hint(rel) or "Game-over screen"
        return "ui_death", "required", hint
    return None


def classify_map(path: str, data: bytes) -> tuple[str, str, str] | None:
    lower = normalize_archive_path(path).lower()
    if not lower.startswith("resource/карта/"):
        return None
    rel = resource_relative(path)
    name = Path(rel).name
    if name == "fon.tga":
        return "map_background", "optional", ENGLISH_SUGGESTIONS.get(name, "City map parchment")
    if not lower.endswith(".qda"):
        return None
    width, height, _frames = qda_dimensions(data)
    kind = classify_map_qda(name, width, height)
    if kind == "label_sprite":
        stem = Path(name).stem.replace("_подсветка", "")
        hint = ENGLISH_SUGGESTIONS.get(stem, f"Map label: {stem}")
        return "map_label", "required", hint
    return "map_click_zone", "skip", "Click/highlight overlay (geometry only — no label text)"


def classify_letters(path: str) -> tuple[str, str, str] | None:
    kind = classify_letter_asset(path)
    if not kind:
        return None
    priority = translate_hint(kind)
    if kind == "inventory_icon":
        name = Path(normalize_archive_path(path)).name.lower()
        if "_inv_описание" in name or "на мыши крупно" in name:
            priority = "required"
        else:
            priority = "optional"
    if kind == "scene_letter":
        priority = "optional"
    hint = letter_english_hint(path, kind)
    category = {
        "inventory_description_full": "inventory_examine",
        "inventory_description_short": "inventory_tooltip",
        "inventory_icon": "inventory_icon",
        "scene_closeup": "scene_document",
        "scene_letter": "scene_prop",
        "static_art": "scene_static",
    }[kind]
    if priority == "yes":
        priority = "required"
    return category, priority, hint


def classify_scene_extra(path: str, data: bytes) -> tuple[str, str, str] | None:
    lower = normalize_archive_path(path).lower()
    rel = resource_relative(path)
    name = Path(lower).name

    if "заставка стартовая надпись" in lower:
        return "startup_quote", "required", "Startup epigraph (Jaroslav Hašek quote)"

    if lower.startswith("resource/game_portret/"):
        stem = Path(name).stem
        if stem in MINIGAME_PORTRAIT_STEMS:
            return "minigame_portrait", "required", f"Portrait puzzle: {stem}"
        return "minigame_portrait", "skip", "Portrait puzzle animation frame (no readable text)"

    if lower.startswith("resource/final/"):
        return "ending", "required", "End credits / final screen"

    if "game_шкатулка надпись" in lower:
        return "scene_sign", "required", "Jewellery box inscription"

    if any(key in lower for key in SCENE_READABLE_KEYWORDS):
        if is_open_door_false_positive(name):
            return None
        if "_подсветка" in name and "крупный план" not in name:
            return None
        if name.endswith("_inv.qda") or name.endswith("_inv_подсветка.qda"):
            return None
        if "курсор" in lower:
            return None

        width, height, frames = qda_dimensions(data) if lower.endswith(".qda") else (0, 0, 0)
        if lower.endswith(".qda") and width >= 800 and height >= 400:
            priority = "required"
        elif lower.endswith(".tga"):
            priority = "required"
        elif "крупный план" in name or "на мыши крупно" in name:
            priority = "required"
        elif "листовк" in name or "газет" in name or "журнал" in name or "доска" in name:
            priority = "required"
        elif "дело пахана" in name or "донесен" in name:
            priority = "required"
        else:
            priority = "optional"

        if "крупный план" in name:
            category = "scene_document"
        elif "листовк" in name or "газет" in name:
            category = "scene_prop"
        elif "журнал" in name or "дневник" in name:
            category = "scene_journal"
        elif "доска" in name or "розыск" in name:
            category = "scene_sign"
        else:
            category = "scene_prop"

        hint = letter_english_hint(path, category)
        if not hint:
            hint = f"Scene readable graphic: {Path(rel).stem}"
        if frames > 1:
            hint += f" ({frames} frames)"
        return category, priority, hint

    return None


def classify_asset(path: str, data: bytes) -> tuple[str, str, str] | None:
    for classifier in (classify_ui, classify_map, classify_letters, classify_scene_extra):
        if classifier is classify_map:
            result = classifier(path, data)
        elif classifier is classify_scene_extra:
            result = classifier(path, data)
        else:
            result = classifier(path)
        if result:
            category, priority, hint = result
            if priority == "skip":
                return None
            return category, priority, hint
    return None


def retail_bytes(
    archive_path: str,
    pak_index: dict[str, bytes],
    ui_src_root: Path,
) -> tuple[bytes | None, str]:
    rel = resource_relative(archive_path)
    ui_src_path = ui_src_root / rel
    if ui_src_path.exists():
        return ui_src_path.read_bytes(), "ui_src"
    return pak_index.get(archive_path), "pak"


def find_work_png(rel: str, qda_work: Path, letters_png: Path) -> Path | None:
    """Return GIMP workspace PNG if the asset was exported for editing."""
    rel_path = Path(rel)
    candidates = [
        qda_work / rel_path.with_suffix(".png"),
        letters_png / rel_path.with_suffix(".png"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    stem = rel_path.with_suffix("")
    for root in (qda_work, letters_png):
        parent = root / stem.parent
        if not parent.exists():
            continue
        matches = sorted(parent.glob(f"{stem.name}*.png"))
        if matches:
            return matches[0]
    return None


def resolve_status(
    archive_path: str,
    pak_index: dict[str, bytes],
    overrides_dir: Path,
    ui_src_root: Path,
    qda_work: Path,
    letters_png: Path,
) -> tuple[str, str, str]:
    """Return (status, retail_source, work_png_relative)."""
    rel = resource_relative(archive_path)
    override_path = overrides_dir / "Resource" / rel
    work_png = find_work_png(rel, qda_work, letters_png)
    work_rel = str(work_png.relative_to(ROOT)) if work_png else ""

    retail, retail_source = retail_bytes(archive_path, pak_index, ui_src_root)

    if override_path.exists():
        override_bytes = override_path.read_bytes()
        if retail is not None and override_bytes == retail:
            return "packaged", retail_source, work_rel
        return "translated", retail_source, work_rel

    if work_png is not None:
        return "extracted", retail_source, work_rel

    return "pending", retail_source, work_rel


def build_rows(
    pak_path: Path,
    overrides_dir: Path,
    *,
    ui_src_root: Path = DEFAULT_UI_SRC,
    qda_work: Path = DEFAULT_QDA_WORK,
    letters_png: Path = DEFAULT_LETTERS_PNG,
) -> list[dict[str, str]]:
    pak_index = load_pak_index(pak_path)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for archive_path in sorted(pak_index):
        lower = archive_path.lower()
        if not (lower.endswith(".qda") or lower.endswith(".tga")):
            continue

        data = pak_index[archive_path]
        classified = classify_asset(archive_path, data)
        if not classified:
            continue

        if archive_path in seen:
            continue
        seen.add(archive_path)

        category, priority, hint = classified
        rel = resource_relative(archive_path)
        width, height, frames = qda_dimensions(data) if lower.endswith(".qda") else ("", "", "")
        status, retail_source, work_rel = resolve_status(
            archive_path,
            pak_index,
            overrides_dir,
            ui_src_root,
            qda_work,
            letters_png,
        )

        rows.append(
            {
                "archive_path": archive_path,
                "resource_folder": archive_path.split("/")[1] if "/" in archive_path else "",
                "relative_path": rel,
                "filename": Path(rel).name,
                "format": Path(rel).suffix.lower(),
                "category": category,
                "priority": priority,
                "status": status,
                "retail_baseline": retail_source,
                "english_hint": hint,
                "width": str(width) if width else "",
                "height": str(height) if height else "",
                "frames": str(frames) if frames else "",
                "work_png": work_rel,
                "override_path": f"patch/overrides/Resource/{rel}",
                "notes": (
                    "Multi-frame — edit every *_fNN.png in qda_work"
                    if isinstance(frames, int) and frames > 1
                    else ""
                ),
            }
        )

    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    fields = [
        "archive_path",
        "resource_folder",
        "relative_path",
        "filename",
        "format",
        "category",
        "priority",
        "status",
        "retail_baseline",
        "english_hint",
        "width",
        "height",
        "frames",
        "work_png",
        "override_path",
        "notes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, str]]) -> None:
    required = [row for row in rows if row["priority"] == "required"]
    optional = [row for row in rows if row["priority"] != "required"]

    def count_status(subset: list[dict[str, str]], status: str) -> int:
        return sum(1 for row in subset if row["status"] == status)

    print(f"All classified image assets: {len(rows)}")
    print(f"  must translate (required): {len(required)}")
    print(f"  optional / low priority: {len(optional)}")
    print()
    print("Required assets — translation pipeline:")
    for status in ("translated", "packaged", "extracted", "pending"):
        print(f"  {status}: {count_status(required, status)}")
    print()
    print("By category (required only):")
    categories = sorted({row["category"] for row in required})
    for category in categories:
        cat_rows = [row for row in required if row["category"] == category]
        translated = count_status(cat_rows, "translated")
        extracted = count_status(cat_rows, "extracted")
        pending = count_status(cat_rows, "pending")
        print(
            f"  {category}: {len(cat_rows)} total"
            f" — {translated} translated, {extracted} extracted, {pending} pending"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--ui-src", type=Path, default=DEFAULT_UI_SRC)
    parser.add_argument("--qda-work", type=Path, default=DEFAULT_QDA_WORK)
    parser.add_argument("--letters-png", type=Path, default=DEFAULT_LETTERS_PNG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    rows = build_rows(
        pak,
        args.overrides,
        ui_src_root=args.ui_src,
        qda_work=args.qda_work,
        letters_png=args.letters_png,
    )
    write_csv(rows, args.output)
    print_summary(rows)
    print(f"CSV: {args.output}")


if __name__ == "__main__":
    main()