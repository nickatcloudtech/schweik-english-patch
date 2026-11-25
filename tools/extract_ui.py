#!/usr/bin/env python3
"""Extract UI graphics and cursor assets from resource0.pak for English editing."""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pak_paths import decode_pak_path

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OUTPUT = ROOT / "patch" / "ui_src"

UI_PREFIXES = (
    "Resource\\Interface\\",
    "Resource\\Inventory\\",
    "Resource\\Экран смерти\\",
)

CURSOR_HINTS = (
    "Resource\\Cursors\\",
    "курсор",
    "cursor",
)


def describe_asset(path: str) -> str:
    lower = path.lower()
    if "main menu" in lower and "fon.tga" in lower:
        return "Main menu background (likely game title art)"
    if "save" in lower and lower.endswith(".tga"):
        return "Save screen background"
    if "load" in lower and lower.endswith(".tga"):
        return "Load screen background"
    if "exit" in lower and lower.endswith(".tga"):
        return "Exit confirmation background"
    if "re-save" in lower and lower.endswith(".tga"):
        return "Overwrite save prompt background"
    if "экран смерти" in lower:
        return "Game-over screen asset"
    if "inventory" in lower or "инвентар" in lower:
        return "Inventory UI asset"
    if "кнопка меню" in lower:
        return "In-game menu button"
    if "new game" in lower or "load" in lower or "save" in lower or "resume" in lower:
        return "Main menu button states"
    if "yes" in lower or "no" in lower or "to main" in lower:
        return "Dialog button states"
    if "курсор" in lower or "cursors" in lower:
        return "Mouse cursor asset"
    if lower.endswith(".qda"):
        return "Animated UI/control graphic (button states)"
    if lower.endswith(".tga"):
        return "Static UI background/panel"
    return "UI asset"


def should_extract(path: str, *, cursors: bool, interface: bool, inventory: bool) -> bool:
    if cursors and any(hint in path for hint in CURSOR_HINTS):
        return True
    if interface and path.startswith("Resource\\Interface\\"):
        return True
    if inventory and path.startswith("Resource\\Inventory\\"):
        return True
    if interface and path.startswith("Resource\\Экран смерти\\"):
        return True
    return False


def extract_assets(
    pak_path: Path,
    output_dir: Path,
    *,
    cursors: bool,
    interface: bool,
    inventory: bool,
) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []

    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            path = decode_pak_path(raw_name)
            if not should_extract(path, cursors=cursors, interface=interface, inventory=inventory):
                continue

            out_path = output_dir / path.replace("\\", "/")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(archive.read(raw_name))
            manifest_rows.append(
                {
                    "archive_path": path,
                    "local_path": str(out_path.relative_to(output_dir)),
                    "format": out_path.suffix.lower(),
                    "description": describe_asset(path),
                }
            )

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["archive_path", "local_path", "format", "description"],
        )
        writer.writeheader()
        writer.writerows(sorted(manifest_rows, key=lambda row: row["archive_path"]))

    return manifest_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cursors", action="store_true", help="Include cursor assets")
    parser.add_argument("--interface", action="store_true", help="Include Interface/ screens")
    parser.add_argument("--inventory", action="store_true", help="Include Inventory/ assets")
    parser.add_argument("--all", action="store_true", help="Extract cursors + interface + inventory")
    args = parser.parse_args()

    if args.all:
        args.cursors = True
        args.interface = True
        args.inventory = True

    if not (args.cursors or args.interface or args.inventory):
        parser.error("Choose at least one of --cursors, --interface, --inventory, or --all")

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    rows = extract_assets(
        pak,
        args.output,
        cursors=args.cursors,
        interface=args.interface,
        inventory=args.inventory,
    )
    print(f"Extracted {len(rows)} files to {args.output}")
    print(f"Manifest: {args.output / 'manifest.csv'}")


if __name__ == "__main__":
    main()