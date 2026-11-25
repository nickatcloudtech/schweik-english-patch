#!/usr/bin/env python3
"""Verify main-menu button QDAs are deployed and differ from retail where expected."""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qda_tools import decode_rle_frame, parse_qda
from tools.pak_paths import decode_pak_path
from tools.scummvm_loose import scummvm_loose_visible
from tools.tga_convert import ensure_engine_tga

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OVERRIDES = ROOT / "patch" / "overrides"
DEFAULT_UI_SRC = ROOT / "patch" / "ui_src" / "Resource"
DEFAULT_WORK = ROOT / "patch" / "qda_work"
DEFAULT_RESOURCE_LOOSE = ROOT / "patch" / "resource_loose" / "Resource"

MENU_SHALLOW = (
    "Interface/Main menu/fon.tga",
    "Interface/Main menu/music.qda",
    "Interface/Main menu/zvuk.qda",
)

MENU_BUTTONS = (
    "Interface/Main menu/new game/new_active.qda",
    "Interface/Main menu/load/load_active.qda",
    "Interface/Main menu/save/save_active.qda",
    "Interface/Main menu/resume/resume_active.qda",
    "Interface/Main menu/exit/exit_active.qda",
)


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def deploy_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() == ".tga":
        return ensure_engine_tga(data, path)
    return data


def opaque_pixels(path: Path) -> int:
    frame = parse_qda(path.read_bytes()).frames[0]
    image = decode_rle_frame(frame)
    crop = image.crop(
        (
            frame.offset_x,
            frame.offset_y,
            frame.offset_x + frame.picture_w,
            frame.offset_y + frame.picture_h,
        )
    )
    pixels = crop.convert("RGBA").load()
    return sum(
        1
        for y in range(crop.height)
        for x in range(crop.width)
        if pixels[x, y][3] > 0
    )


def verify(game_dir: Path, overrides_dir: Path, ui_src: Path, work_dir: Path) -> int:
    resource = game_dir / "Resource"
    interface_dir = resource / "Interface"
    if not interface_dir.exists():
        print(f"FAIL: missing {interface_dir}")
        return 1

    loose_files = [path for path in interface_dir.rglob("*") if path.is_file()]
    loose_count = len(loose_files)
    nested_on_disk = [
        path
        for path in loose_files
        if not scummvm_loose_visible(Path("Resource") / path.relative_to(resource))
    ]
    if nested_on_disk:
        print(f"FAIL: {len(nested_on_disk)} nested Interface file(s) should not be loose")
        for path in nested_on_disk[:5]:
            print(f"  - {path.relative_to(resource)}")
        print("  Run ./deploy — nested menu QDAs must load from resource0.pak only")
        return 1

    cache_iface = DEFAULT_RESOURCE_LOOSE / "Interface"
    expected_loose = sum(
        1
        for path in cache_iface.rglob("*")
        if path.is_file()
        and scummvm_loose_visible(Path("Resource") / path.relative_to(cache_iface.parent))
    )
    if loose_count != expected_loose:
        print(f"FAIL: expected {expected_loose} loose Interface files, found {loose_count}")
        print("  Run ./deploy — partial Interface/ breaks Load/Exit on ScummVM")
        return 1

    print(f"OK: {loose_count} loose Interface files (+ nested button QDAs in pak)")
    errors: list[str] = []

    for rel in (*MENU_SHALLOW, *MENU_BUTTONS):
        retail = ui_src / rel
        override = overrides_dir / "Resource" / rel
        game = resource / rel
        work_png = (work_dir / rel).with_suffix(".png")

        expected = deploy_bytes(override) if override.exists() else None
        loose_visible = scummvm_loose_visible(Path("Resource") / Path(rel))

        if loose_visible:
            if not game.exists():
                errors.append(f"{rel}: missing loose in game folder")
                continue
            if expected is not None and md5_bytes(game.read_bytes()) != md5_bytes(expected):
                errors.append(f"{rel}: game file does not match patch/overrides (deployed form)")
        elif expected is not None:
            if game.exists():
                errors.append(f"{rel}: nested file must not be loose (run ./deploy to prune)")
        else:
            if not game.exists():
                errors.append(f"{rel}: missing in game folder")
                continue

        if expected is not None:
            pak = resource / "resource0.pak"
            if pak.exists():
                archive_key = f"resource/{rel}".replace("\\", "/").lower()
                with zipfile.ZipFile(pak, "r") as archive:
                    members = {
                        decode_pak_path(name).replace("\\", "/").lower(): name
                        for name in archive.namelist()
                    }
                    member = members.get(archive_key)
                    if not member:
                        errors.append(f"{rel}: missing from resource0.pak")
                    elif md5_bytes(archive.read(member)) != md5_bytes(expected):
                        errors.append(
                            f"{rel}: resource0.pak still has retail art (run ./deploy to inject)"
                        )
        elif not loose_visible and not game.exists():
            errors.append(f"{rel}: missing from resource0.pak and game folder")

        translated = override.exists() and retail.exists() and md5(override) != md5(retail)
        has_work = work_png.exists()
        check_path = game if game.exists() else (override if override.exists() else retail)
        if check_path.suffix.lower() == ".qda":
            visible = opaque_pixels(check_path)
            visible_note = f"{visible} visible pixels"
        elif check_path.exists():
            visible_note = f"{check_path.stat().st_size} bytes"
        else:
            visible_note = "missing"
        status = "translated" if translated else ("packaged" if override.exists() else "retail")
        print(
            f"  {Path(rel).parent.name}/{Path(rel).name}: {status}, "
            f"{visible_note}, work_png={'yes' if has_work else 'no'}"
        )

    if errors:
        print("Menu verification FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: main-menu QDAs deployed. Fully quit and restart ScummVM after ./deploy.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--ui-src", type=Path, default=DEFAULT_UI_SRC)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    args = parser.parse_args()
    raise SystemExit(verify(args.game_dir, args.overrides, args.ui_src, args.work))


if __name__ == "__main__":
    main()