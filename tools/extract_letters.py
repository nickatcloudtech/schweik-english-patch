#!/usr/bin/env python3
"""Extract in-game letters, messages, and readable documents for translation.

Readable text is baked into QDA/TGA art (not in schweik_dialogue.csv). This tool
pulls letter-related assets from resource0.pak and exports PNGs for GIMP.

Output layout:
  patch/letters/src/   — raw QDA/TGA from the pak
  patch/letters/png/   — exported PNGs (multi-frame QDAs use *_f00.png, …)
  patch/letters/manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pak_paths import decode_pak_path
from tools.qda_tools import parse_qda, qda_to_pngs
from tools.tga_convert import ensure_engine_tga

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_SRC = ROOT / "patch" / "letters" / "src"
DEFAULT_PNG = ROOT / "patch" / "letters" / "png"
DEFAULT_MANIFEST = ROOT / "patch" / "letters" / "manifest.csv"

INVENTORY_TEXT_ITEMS = (
    "открытк",
    "письм",
    "послан",
    "конверт",
    "шифров",
    "документ",
    "текст письма",
    "донесение",
    "повестка",
    "бумажка",
    "листовка",
)

SCENE_KEYWORDS = INVENTORY_TEXT_ITEMS + ("записк", "газет")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def stem_lower(path: str) -> str:
    return Path(normalize_path(path)).stem.lower()


def is_open_door_false_positive(name: str) -> bool:
    lower = name.lower()
    if "открытк" in lower:
        return False
    return bool(re.search(r"открыт", lower))


def is_letter_inventory_icon(path: str) -> bool:
    name = Path(normalize_path(path)).name.lower()
    if not name.endswith("_inv.qda") and "_inv_" not in name:
        return False
    if is_open_door_false_positive(name):
        return False
    base = name.replace("_inv.qda", "").replace("_inv_", "_")
    return any(key in base for key in INVENTORY_TEXT_ITEMS)


def description_has_letter_text(name: str) -> bool:
    lower = name.lower()
    return any(key in lower for key in INVENTORY_TEXT_ITEMS + ("записк", "газет"))


def is_inventory_description(path: str) -> bool:
    lower = normalize_path(path).lower()
    if "/инвентарь/описания/desc" not in lower:
        return False
    return description_has_letter_text(Path(lower).stem)


def is_letter_scene_asset(path: str) -> bool:
    lower = normalize_path(path).lower()
    if "/инвентарь/" in lower:
        return False
    name = Path(lower).name
    if is_open_door_false_positive(name):
        return False
    if any(key in name for key in SCENE_KEYWORDS):
        return True
    if "крупный план" in name and any(
        key in name for key in ("письм", "послан", "записк", "конверт", "шифров")
    ):
        return True
    return False


def is_letter_static(path: str) -> bool:
    lower = normalize_path(path).lower()
    return lower.endswith(".tga") and "газет" in lower


def classify_asset(path: str) -> str | None:
    if is_inventory_description(path):
        if "/desc full_" in normalize_path(path).lower():
            return "inventory_description_full"
        return "inventory_description_short"
    if is_letter_inventory_icon(path):
        return "inventory_icon"
    if is_letter_static(path):
        return "static_art"
    if is_letter_scene_asset(path):
        name = Path(normalize_path(path)).name.lower()
        if "крупный план" in name:
            return "scene_closeup"
        return "scene_letter"
    return None


def translate_hint(kind: str) -> str:
    if kind in {
        "inventory_description_full",
        "inventory_description_short",
        "scene_closeup",
        "static_art",
    }:
        return "yes"
    if kind == "scene_letter" and "текст" in kind:
        return "yes"
    return "optional"


def english_hint(path: str, kind: str) -> str:
    name = stem_lower(path)
    hints = {
        "открытк": "Postcard (Schweik's room / Mrs Müller plot)",
        "письмо для сх": "Letter for Sister Hostess (Mrs Müller)",
        "письмо для пм": "Letter for Mrs Müller (from Chaplain Katz)",
        "письмо императора": "Emperor's letter (Lukáš apartment)",
        "письмо на итальянском": "Letter in Italian (jewellery box)",
        "послание для каца": "Message for Katz (train station)",
        "послание2": "Cipher message #2 (crucifix scene)",
        "послание3": "Cipher message #3 (crucifix scene)",
        "послание из центра": "Report from headquarters",
        "текст письма": "Letter body text (readable close-up)",
        "шифровка": "Cipher text (decode with cipher key item)",
        "шифровальный ключ": "Cipher key (inventory description)",
        "документы сестры-хозяйки": "Sister Hostess forged papers",
        "документы из дела пахана": "Gang boss case file papers",
        "газета": "Newspaper (Schweik's room — arson puzzle)",
        "записки с адресом": "Note with address (Mrs Müller's diary)",
        "донесение": "Intelligence report",
        "повестка": "Summons / court notice",
        "листовка": "Flyer (square location)",
        "бумажка": "Scrap of paper with address",
    }
    for key, hint in hints.items():
        if key in name:
            return hint
    if kind.startswith("inventory_description"):
        return "Inventory examine text — translate baked Russian typography"
    if kind == "scene_closeup":
        return "Readable document close-up — translate baked Russian text"
    return ""


def iter_letter_assets(pak_path: Path) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = normalize_path(decode_pak_path(raw_name))
            kind = classify_asset(decoded)
            if kind:
                hits.append((raw_name, decoded, kind))
    return sorted(hits, key=lambda item: item[1].lower())


def extract_sources(pak_path: Path, src_root: Path, assets: list[tuple[str, str, str]]) -> None:
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name, decoded, _kind in assets:
            target = src_root / decoded.replace("Resource/", "", 1)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(raw_name))


def export_pngs(src_root: Path, png_root: Path, assets: list[tuple[str, str, str]]) -> int:
    from PIL import Image

    count = 0
    for _raw, decoded, _kind in assets:
        rel = decoded.replace("Resource/", "", 1)
        source = src_root / rel
        if not source.exists():
            continue
        png_target = (png_root / rel).with_suffix(".png")
        png_target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() == ".qda":
            try:
                qda_to_pngs(source.read_bytes(), png_target)
            except (ValueError, OSError) as exc:
                print(f"skip {rel} ({exc})")
                continue
        elif source.suffix.lower() == ".tga":
            converted = ensure_engine_tga(source.read_bytes(), source)
            Image.open(BytesIO(converted)).save(png_target)
        else:
            continue
        count += 1
        print(f"export {png_target.relative_to(png_root)}")
    return count


def write_manifest(
    assets: list[tuple[str, str, str]],
    src_root: Path,
    manifest_path: Path,
) -> None:
    rows: list[dict[str, str]] = []
    for _raw, decoded, kind in assets:
        rel = decoded.replace("Resource/", "", 1)
        source = src_root / rel
        row = {
            "archive_path": decoded,
            "local_path": str(source.relative_to(src_root.parent)),
            "filename": Path(rel).name,
            "kind": kind,
            "width": "",
            "height": "",
            "frames": "",
            "translate": translate_hint(kind),
            "english_hint": english_hint(decoded, kind),
            "notes": "",
        }
        if source.suffix.lower() == ".qda":
            try:
                animation = parse_qda(source.read_bytes())
            except ValueError as exc:
                row["notes"] = f"unsupported QDA ({exc})"
            else:
                frame = animation.frames[0]
                row["width"] = str(frame.canvas_w)
                row["height"] = str(frame.canvas_h)
                row["frames"] = str(len(animation.frames))
                if len(animation.frames) > 1:
                    row["notes"] = "Multi-frame QDA — edit every *_fNN.png"
        rows.append(row)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--no-png", action="store_true", help="Extract sources only")
    args = parser.parse_args()

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    assets = iter_letter_assets(pak)
    if not assets:
        raise SystemExit("No letter/message assets matched")

    extract_sources(pak, args.src, assets)
    print(f"Extracted {len(assets)} file(s) to {args.src}")

    by_kind: dict[str, int] = {}
    for _raw, _decoded, kind in assets:
        by_kind[kind] = by_kind.get(kind, 0) + 1
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind}: {count}")

    write_manifest(assets, args.src, args.manifest)
    print(f"Manifest: {args.manifest}")

    if not args.no_png:
        exported = export_pngs(args.src, args.png, assets)
        print(f"Exported {exported} PNG set(s) to {args.png}")
        print("Edit readable text in GIMP, then pack with qda_edit.py import when overrides are ready.")


if __name__ == "__main__":
    main()