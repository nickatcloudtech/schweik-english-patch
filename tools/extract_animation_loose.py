#!/usr/bin/env python3
"""Extract loose Resource files ScummVM needs when patch overrides shadow the pak.

ScummVM does not fall back to resource0.pak for files missing under a loose
Resource/ folder. A partial folder breaks characters, inventory backgrounds,
and room animations.

This tool builds a unified cache under patch/resource_loose/Resource/<folder>/:
  - Always: Animation (255 top-level QDAs), Sound, Music, Инвентарь (238 files)
  - When overrides exist: Interface, Inventory (UI strip), any room/scene folder
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pak_paths import decode_pak_path

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_RESOURCE_LOOSE_ROOT = ROOT / "patch" / "resource_loose" / "Resource"
DEFAULT_OVERRIDES = ROOT / "patch" / "overrides"
DEFAULT_PAK = DEFAULT_GAME / "Resource" / "resource0.pak"

# Cyrillic folder: inventory item icons, letter close-ups, desc full_* examine screens.
INVENTORY_ITEMS_FOLDER = "Инвентарь"

# Deploy full pak tree for these on every ./deploy (Cyrillic paths fail in pak on ScummVM).
ALWAYS_LOOSE_FOLDERS = frozenset({"Animation", "Sound", "Music", INVENTORY_ITEMS_FOLDER})

# Deploy full tree only when patch/overrides touches that folder.
CONDITIONAL_LOOSE_FOLDERS = frozenset({"Interface", "Inventory"})

# Never auto-discover these as override-driven room caches (handled above).
DISCOVER_SKIP_FOLDERS = ALWAYS_LOOSE_FOLDERS | CONDITIONAL_LOOSE_FOLDERS | frozenset({"Cursors"})

# Backward-compatible aliases (all under resource_loose now).
DEFAULT_ANIMATION_CACHE = DEFAULT_RESOURCE_LOOSE_ROOT / "Animation"
DEFAULT_INVENTORY_CACHE = DEFAULT_RESOURCE_LOOSE_ROOT / "Inventory"
DEFAULT_ROOM_CACHE_ROOT = DEFAULT_RESOURCE_LOOSE_ROOT
DEFAULT_SOUND_CACHE = DEFAULT_RESOURCE_LOOSE_ROOT / "Sound"
DEFAULT_MUSIC_CACHE = DEFAULT_RESOURCE_LOOSE_ROOT / "Music"
DEFAULT_INTERFACE_CACHE = DEFAULT_RESOURCE_LOOSE_ROOT / "Interface"
DEFAULT_INVENTORY_ITEMS_CACHE = DEFAULT_RESOURCE_LOOSE_ROOT / INVENTORY_ITEMS_FOLDER

EXPECTED_TOP_LEVEL_ANIMATIONS = 255
EXPECTED_SOUND_FILES = 205
EXPECTED_MUSIC_FILES = 4
EXPECTED_INTERFACE_FILES = 49
EXPECTED_INVENTORY_UI_FILES = 6
EXPECTED_INVENTORY_ITEMS_FILES = 238


def normalize_resource_path(path: str) -> str:
    return path.replace("\\", "/")


def path_parts(path: str) -> list[str]:
    return normalize_resource_path(path).split("/")


def is_top_level_animation(decoded_path: str) -> bool:
    parts = path_parts(decoded_path)
    return (
        len(parts) == 3
        and parts[0] == "Resource"
        and parts[1] == "Animation"
        and parts[2].lower().endswith(".qda")
    )


def is_resource_folder_file(decoded_path: str, folder: str) -> bool:
    parts = path_parts(decoded_path)
    return len(parts) >= 3 and parts[0] == "Resource" and parts[1] == folder


def is_room_resource(decoded_path: str, room: str) -> bool:
    parts = path_parts(decoded_path)
    return len(parts) >= 3 and parts[0] == "Resource" and parts[1] == room


def discover_override_resource_folders(overrides_dir: Path) -> list[str]:
    """Top-level Resource/<folder>/ with any override file (map, scenes, death screen, etc.)."""
    resource_root = overrides_dir / "Resource"
    if not resource_root.exists():
        return []

    folders: list[str] = []
    for entry in sorted(resource_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in DISCOVER_SKIP_FOLDERS:
            continue
        if any(entry.rglob("*")):
            folders.append(entry.name)
    return folders


def discover_room_animation_overrides(overrides_dir: Path) -> list[str]:
    return discover_override_resource_folders(overrides_dir)


def discover_room_resource_overrides(overrides_dir: Path) -> list[str]:
    return discover_override_resource_folders(overrides_dir)


def _write_member(archive: zipfile.ZipFile, raw_name: str, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    data = archive.read(raw_name)
    target.write_bytes(data)
    return len(data)


def count_pak_folder_files(pak_path: Path, folder: str) -> int:
    prefix = f"Resource/{folder}/"
    count = 0
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = normalize_resource_path(decode_pak_path(raw_name))
            if decoded.startswith(prefix):
                count += 1
    return count


def pak_folder_relative_paths(pak_path: Path, folder: str) -> set[str]:
    prefix = f"Resource/{folder}/"
    paths: set[str] = set()
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = normalize_resource_path(decode_pak_path(raw_name))
            if decoded.startswith(prefix):
                paths.add(decoded[len(prefix) :])
    return paths


def count_cache_files(cache_dir: Path) -> int:
    if not cache_dir.exists():
        return 0
    return sum(1 for path in cache_dir.rglob("*") if path.is_file())


def cache_relative_paths(cache_dir: Path) -> set[str]:
    if not cache_dir.exists():
        return set()
    return {
        path.relative_to(cache_dir).as_posix()
        for path in cache_dir.rglob("*")
        if path.is_file()
    }


def extract_animation_loose(pak_path: Path, output_dir: Path) -> int:
    """Extract every top-level Resource/Animation/*.qda from the pak (flat, no subdirs)."""
    if not pak_path.exists():
        raise FileNotFoundError(f"Missing {pak_path}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    total = 0
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = decode_pak_path(raw_name)
            if not is_top_level_animation(decoded):
                continue
            filename = Path(normalize_resource_path(decoded)).name
            total += _write_member(archive, raw_name, output_dir / filename)
            count += 1

    print(
        f"Extracted {count} top-level Animation QDA(s) "
        f"({total / 1024 / 1024:.1f} MB) to {output_dir}"
    )
    if count != EXPECTED_TOP_LEVEL_ANIMATIONS:
        print(f"  warning: expected {EXPECTED_TOP_LEVEL_ANIMATIONS}, got {count}")
    return count


def extract_resource_folder_loose(pak_path: Path, folder: str, output_dir: Path) -> int:
    """Extract every file under Resource/<folder>/ from the pak."""
    if not pak_path.exists():
        raise FileNotFoundError(f"Missing {pak_path}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    total = 0
    prefix = f"Resource/{folder}/"
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = normalize_resource_path(decode_pak_path(raw_name))
            if not decoded.startswith(prefix):
                continue
            relative = decoded[len(prefix) :]
            total += _write_member(archive, raw_name, output_dir / relative)
            count += 1

    print(
        f"Extracted {count} {folder} file(s) "
        f"({total / 1024 / 1024:.1f} MB) to {output_dir}"
    )
    return count


# Backward-compatible wrappers used by verify_animations.py and older docs.
def extract_inventory_loose(pak_path: Path, output_dir: Path) -> int:
    return extract_resource_folder_loose(pak_path, "Inventory", output_dir)


def extract_room_resource_loose(pak_path: Path, room: str, output_dir: Path) -> int:
    return extract_resource_folder_loose(pak_path, room, output_dir)


def extract_sound_loose(pak_path: Path, output_dir: Path) -> int:
    return extract_resource_folder_loose(pak_path, "Sound", output_dir)


def extract_music_loose(pak_path: Path, output_dir: Path) -> int:
    return extract_resource_folder_loose(pak_path, "Music", output_dir)


def extract_interface_loose(pak_path: Path, output_dir: Path) -> int:
    return extract_resource_folder_loose(pak_path, "Interface", output_dir)


def extract_inventory_items_loose(pak_path: Path, output_dir: Path) -> int:
    return extract_resource_folder_loose(pak_path, INVENTORY_ITEMS_FOLDER, output_dir)


def expected_file_count(folder: str) -> int | None:
    return {
        "Animation": EXPECTED_TOP_LEVEL_ANIMATIONS,
        "Sound": EXPECTED_SOUND_FILES,
        "Music": EXPECTED_MUSIC_FILES,
        "Interface": EXPECTED_INTERFACE_FILES,
        "Inventory": EXPECTED_INVENTORY_UI_FILES,
        INVENTORY_ITEMS_FOLDER: EXPECTED_INVENTORY_ITEMS_FILES,
    }.get(folder)


def folder_cache_is_stale(cache_dir: Path, folder: str, pak_path: Path) -> bool:
    if not cache_dir.exists():
        return True

    cached = count_cache_files(cache_dir)
    expected = expected_file_count(folder)
    if expected is not None:
        if folder == "Animation":
            cached = len(list(cache_dir.glob("*.qda")))
        return cached != expected

    pak_count = count_pak_folder_files(pak_path, folder)
    return cached != pak_count or cached == 0


def animation_cache_is_stale(cache_dir: Path) -> bool:
    if not cache_dir.exists():
        return True
    return len(list(cache_dir.glob("*.qda"))) != EXPECTED_TOP_LEVEL_ANIMATIONS


def inventory_cache_is_stale(cache_dir: Path) -> bool:
    return folder_cache_is_stale(cache_dir, "Inventory", DEFAULT_PAK)


def room_cache_is_stale(cache_dir: Path) -> bool:
    if not cache_dir.exists():
        return True
    return not any(cache_dir.rglob("*"))


def sound_cache_is_stale(cache_dir: Path) -> bool:
    return folder_cache_is_stale(cache_dir, "Sound", DEFAULT_PAK)


def music_cache_is_stale(cache_dir: Path) -> bool:
    return folder_cache_is_stale(cache_dir, "Music", DEFAULT_PAK)


def interface_cache_is_stale(cache_dir: Path) -> bool:
    return folder_cache_is_stale(cache_dir, "Interface", DEFAULT_PAK)


def inventory_items_cache_is_stale(cache_dir: Path) -> bool:
    return folder_cache_is_stale(cache_dir, INVENTORY_ITEMS_FOLDER, DEFAULT_PAK)


def folders_to_cache(overrides_dir: Path) -> list[str]:
    folders = list(ALWAYS_LOOSE_FOLDERS)
    for folder in sorted(CONDITIONAL_LOOSE_FOLDERS):
        if (overrides_dir / "Resource" / folder).exists():
            folders.append(folder)
    folders.extend(discover_override_resource_folders(overrides_dir))
    return folders


def build_loose_caches(
    pak_path: Path,
    *,
    resource_root: Path = DEFAULT_RESOURCE_LOOSE_ROOT,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    force: bool = False,
    # Backward-compatible kwargs (ignored except as aliases for resource_root children).
    animation_dir: Path | None = None,
    inventory_dir: Path | None = None,
    room_cache_root: Path | None = None,
    sound_dir: Path | None = None,
    music_dir: Path | None = None,
    interface_dir: Path | None = None,
) -> dict[str, int]:
    if animation_dir is not None:
        resource_root = animation_dir.parent
    elif inventory_dir is not None:
        resource_root = inventory_dir.parent
    elif room_cache_root is not None:
        resource_root = room_cache_root
    elif sound_dir is not None:
        resource_root = sound_dir.parent

    counts: dict[str, int] = {}
    for folder in folders_to_cache(overrides_dir):
        cache_dir = resource_root / folder
        stale = force
        if not stale:
            if folder == "Animation":
                stale = animation_cache_is_stale(cache_dir)
            else:
                stale = folder_cache_is_stale(cache_dir, folder, pak_path)

        if stale:
            if folder == "Animation":
                counts[folder] = extract_animation_loose(pak_path, cache_dir)
            else:
                counts[folder] = extract_resource_folder_loose(pak_path, folder, cache_dir)
        else:
            if folder == "Animation":
                counts[folder] = len(list(cache_dir.glob("*.qda")))
            else:
                counts[folder] = count_cache_files(cache_dir)

    counts["rooms"] = len(discover_override_resource_folders(overrides_dir))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--pak", type=Path, default=None)
    parser.add_argument("--resource-root", type=Path, default=DEFAULT_RESOURCE_LOOSE_ROOT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--force", action="store_true", help="Rebuild caches even if present")
    args = parser.parse_args()

    pak = args.pak or (args.game_dir / "Resource" / "resource0.pak")
    counts = build_loose_caches(
        pak.resolve(),
        resource_root=args.resource_root.resolve(),
        overrides_dir=args.overrides.resolve(),
        force=args.force,
    )
    parts = [f"{name}={count}" for name, count in sorted(counts.items()) if name != "rooms"]
    print(f"Cache summary: {', '.join(parts)}")
    if counts.get("rooms"):
        print(f"  override-driven room folders: {counts['rooms']}")


if __name__ == "__main__":
    main()