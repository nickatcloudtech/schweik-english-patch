#!/usr/bin/env python3
"""Verify ScummVM loose animation/inventory caches cover QML references."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.extract_animation_loose import (
    DEFAULT_ANIMATION_CACHE,
    DEFAULT_INVENTORY_CACHE,
    DEFAULT_OVERRIDES,
    DEFAULT_ROOM_CACHE_ROOT,
    EXPECTED_TOP_LEVEL_ANIMATIONS,
    discover_room_animation_overrides,
    normalize_resource_path,
)
from tools.pak_paths import decode_pak_path

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"


def qml_animation_filenames(qml_path: Path) -> set[str]:
    text = qml_path.read_bytes().decode("cp1251", errors="replace")
    return set(re.findall(r"Animation[\\/][^\x00\"]+\.qda", text, flags=re.IGNORECASE))


def top_level_animation_names(pak_path: Path) -> set[str]:
    names: set[str] = set()
    with zipfile.ZipFile(pak_path, "r") as archive:
        for raw_name in archive.namelist():
            decoded = normalize_resource_path(decode_pak_path(raw_name))
            parts = decoded.split("/")
            if (
                len(parts) == 3
                and parts[0] == "Resource"
                and parts[1] == "Animation"
                and parts[2].lower().endswith(".qda")
            ):
                names.add(parts[2])
    return names


def verify(
    game_dir: Path,
    animation_cache: Path,
    inventory_cache: Path,
    room_cache_root: Path,
    overrides_dir: Path,
) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    qml = game_dir / "qd_game.qml"
    if not pak.exists():
        raise FileNotFoundError(f"Missing {pak}")
    if not qml.exists():
        raise FileNotFoundError(f"Missing {qml}")

    errors: list[str] = []

    cached_anim = {path.name for path in animation_cache.glob("*.qda")} if animation_cache.exists() else set()
    if len(cached_anim) != EXPECTED_TOP_LEVEL_ANIMATIONS:
        errors.append(
            f"animation cache has {len(cached_anim)} file(s), expected {EXPECTED_TOP_LEVEL_ANIMATIONS}"
        )

    pak_top = top_level_animation_names(pak)
    qml_refs = {Path(ref.replace("\\", "/")).name for ref in qml_animation_filenames(qml)}
    qml_top_refs = qml_refs & pak_top
    missing_top = sorted(qml_top_refs - cached_anim)
    if missing_top:
        errors.append(
            f"{len(missing_top)} top-level Animation QDA(s) referenced in qd_game.qml "
            f"but missing from cache, e.g. {missing_top[:5]}"
        )

    if (overrides_dir / "Resource" / "Inventory").exists():
        cached_inv = {path.name for path in inventory_cache.iterdir()} if inventory_cache.exists() else set()
        with zipfile.ZipFile(pak, "r") as archive:
            pak_inv = {
                Path(normalize_resource_path(decode_pak_path(raw_name))).name
                for raw_name in archive.namelist()
                if normalize_resource_path(decode_pak_path(raw_name)).startswith("Resource/Inventory/")
            }
        missing_inv = sorted(pak_inv - cached_inv)
        if missing_inv:
            errors.append(
                f"{len(missing_inv)} Inventory file(s) missing from cache, e.g. {missing_inv[:5]}"
            )

    for room in discover_room_animation_overrides(overrides_dir):
        room_cache = room_cache_root / room
        cached_room = {
            path.relative_to(room_cache).as_posix()
            for path in room_cache.rglob("*")
            if path.is_file()
        } if room_cache.exists() else set()
        with zipfile.ZipFile(pak, "r") as archive:
            pak_room = {
                normalize_resource_path(decode_pak_path(raw_name)).removeprefix(f"Resource/{room}/")
                for raw_name in archive.namelist()
                if normalize_resource_path(decode_pak_path(raw_name)).startswith(f"Resource/{room}/")
            }
        missing_room = sorted(pak_room - cached_room)
        if missing_room:
            errors.append(
                f"{room}: {len(missing_room)} file(s) missing from cache, "
                f"e.g. {missing_room[:5]}"
            )

    if errors:
        print("Animation verification FAILED:")
        for error in errors:
            print(f"  - {error}")
        print("Rebuild caches: python3 tools/extract_animation_loose.py --force && ./deploy")
        return 1

    print(
        f"OK: {len(cached_anim)} top-level Animation, "
        f"{len(qml_top_refs)} QML top-level refs covered"
    )
    if (overrides_dir / "Resource" / "Inventory").exists():
        print(f"OK: {len(list(inventory_cache.iterdir()))} Inventory cache file(s)")
    rooms = discover_room_animation_overrides(overrides_dir)
    if rooms:
        print(f"OK: room Animation cache for {', '.join(rooms)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--animation-cache", type=Path, default=DEFAULT_ANIMATION_CACHE)
    parser.add_argument("--inventory-cache", type=Path, default=DEFAULT_INVENTORY_CACHE)
    parser.add_argument("--room-cache-root", type=Path, default=DEFAULT_ROOM_CACHE_ROOT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    args = parser.parse_args()
    raise SystemExit(
        verify(
            args.game_dir,
            args.animation_cache,
            args.inventory_cache,
            args.room_cache_root,
            args.overrides,
        )
    )


if __name__ == "__main__":
    main()