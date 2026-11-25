#!/usr/bin/env python3
"""Verify ScummVM loose Resource caches are complete vs resource0.pak.

Run before ./deploy when adding image overrides. A partial loose folder breaks
assets ScummVM would otherwise load from the pak.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.extract_animation_loose import (
    ALWAYS_LOOSE_FOLDERS,
    CONDITIONAL_LOOSE_FOLDERS,
    DEFAULT_OVERRIDES,
    DEFAULT_RESOURCE_LOOSE_ROOT,
    INVENTORY_ITEMS_FOLDER,
    cache_relative_paths,
    discover_override_resource_folders,
    expected_file_count,
    is_top_level_animation,
    pak_folder_relative_paths,
)
from tools.pak_paths import decode_pak_path

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"


def verify_folder(
    pak_path: Path,
    resource_root: Path,
    folder: str,
    *,
    required: bool,
) -> list[str]:
    cache_dir = resource_root / folder
    errors: list[str] = []

    if not cache_dir.exists() or not any(cache_dir.rglob("*")):
        if required:
            errors.append(f"{folder}: cache missing or empty ({cache_dir})")
        return errors

    if folder == "Animation":
        pak_paths: set[str] = set()
        with zipfile.ZipFile(pak_path, "r") as archive:
            for raw_name in archive.namelist():
                decoded = decode_pak_path(raw_name).replace("\\", "/")
                if is_top_level_animation(decoded):
                    pak_paths.add(Path(decoded).name)
        cached_paths = {path.name for path in cache_dir.glob("*.qda")}
    else:
        pak_paths = pak_folder_relative_paths(pak_path, folder)
        cached_paths = cache_relative_paths(cache_dir)

    missing = sorted(pak_paths - cached_paths)
    extra = sorted(cached_paths - pak_paths)

    if missing:
        errors.append(
            f"{folder}: {len(missing)} pak file(s) missing from cache, "
            f"e.g. {missing[:3]}"
        )
    if extra:
        errors.append(
            f"{folder}: {len(extra)} unexpected cache file(s), e.g. {extra[:3]}"
        )

    expected = expected_file_count(folder)
    if expected is not None and len(cached_paths) != expected:
        errors.append(
            f"{folder}: cache has {len(cached_paths)} file(s), expected {expected}"
        )

    return errors


def verify(
    game_dir: Path,
    resource_root: Path,
    overrides_dir: Path,
) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise FileNotFoundError(f"Missing {pak}")

    errors: list[str] = []

    for folder in sorted(ALWAYS_LOOSE_FOLDERS):
        errors.extend(
            verify_folder(pak, resource_root, folder, required=True)
        )

    for folder in sorted(CONDITIONAL_LOOSE_FOLDERS):
        required = (overrides_dir / "Resource" / folder).exists()
        errors.extend(
            verify_folder(pak, resource_root, folder, required=required)
        )

    for folder in discover_override_resource_folders(overrides_dir):
        errors.extend(
            verify_folder(pak, resource_root, folder, required=True)
        )

    if errors:
        print("Loose cache verification FAILED:")
        for error in errors:
            print(f"  - {error}")
        print("Rebuild: python3 tools/extract_animation_loose.py --force && ./deploy")
        return 1

    print("OK: loose caches cover all required Resource folders")
    for folder in sorted(ALWAYS_LOOSE_FOLDERS):
        count = len(cache_relative_paths(resource_root / folder))
        note = ""
        if folder == INVENTORY_ITEMS_FOLDER:
            note = " (letters, item icons, examine screens)"
        print(f"  {folder}: {count} file(s){note}")

    conditional = [
        folder
        for folder in CONDITIONAL_LOOSE_FOLDERS
        if (overrides_dir / "Resource" / folder).exists()
    ]
    for folder in conditional:
        print(f"  {folder}: {len(cache_relative_paths(resource_root / folder))} file(s)")

    rooms = discover_override_resource_folders(overrides_dir)
    if rooms:
        print(f"  override rooms: {', '.join(rooms)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--resource-root", type=Path, default=DEFAULT_RESOURCE_LOOSE_ROOT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    args = parser.parse_args()
    raise SystemExit(verify(args.game_dir, args.resource_root, args.overrides))


if __name__ == "__main__":
    main()