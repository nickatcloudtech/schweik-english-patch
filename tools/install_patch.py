#!/usr/bin/env python3
"""
Install the Schweik English patch into an existing game folder.

No recompile required — only replaces files inside resource0.pak.
Works with the original shveik.exe from the retail game.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.btdb import read_btdb_from_bytes, write_btdb
from tools.import_text import import_dialogue
from tools.inject_ui import collect_ui_files
from tools.pak_paths import decode_pak_path
from tools.pak_utils import (
    backup_file,
    collect_voice_files,
    inject_files,
    replace_member,
    restore_backup,
)

PATCH_DIR = ROOT / "patch"
DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OVERRIDES = PATCH_DIR / "overrides"


def merge_cd_paks(game_dir: Path) -> None:
    import zipfile

    resource = game_dir / "Resource"
    r0 = resource / "resource0.pak"
    r1 = resource / "resource1.pak"
    if not r1.exists():
        print("No resource1.pak — skipping no-CD merge (already merged or CD install).")
        return

    print("Merging resource1.pak into resource0.pak for no-CD play...")
    backup_file(r0)
    backup_file(r1)
    merged = resource / "resource0_merged.pak"

    with zipfile.ZipFile(r0, "r") as z0:
        names0 = set(z0.namelist())
    added = 0
    with zipfile.ZipFile(r0, "r") as z0, zipfile.ZipFile(r1, "r") as z1:
        with zipfile.ZipFile(merged, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for item in z0.infolist():
                out.writestr(item, z0.read(item.filename))
            for item in z1.infolist():
                if item.filename not in names0:
                    out.writestr(item, z1.read(item.filename))
                    added += 1
    merged.replace(r0)
    print(f"Merged {added} files from CD2 into resource0.pak")


def install_subtitles(game_dir: Path, csv_path: Path, btdb_path: Path | None) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise FileNotFoundError(f"Game not found: {pak}")

    if btdb_path and btdb_path.exists():
        english_btdb = btdb_path.read_bytes()
        print(f"Using pre-built text DB: {btdb_path}")
    else:
        temp_btdb = PATCH_DIR / "shveik_en.btdb"
        temp_btdb.parent.mkdir(parents=True, exist_ok=True)
        translated = import_dialogue(csv_path, game_dir, temp_btdb)
        if translated == 0:
            raise SystemExit(
                "No translated lines found in CSV. Fill the 'english' column first, "
                "or ship a pre-built patch/shveik_en.btdb."
            )
        english_btdb = temp_btdb.read_bytes()

    print("Installing English dialogue (updates resource0.pak — may take 1-3 minutes)...")
    member = replace_member(pak, "shveik.btdb", english_btdb)
    print(f"Installed English subtitles via {member}")
    return len(read_btdb_from_bytes(english_btdb))


def install_graphics(game_dir: Path, overrides_dir: Path) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    files = collect_ui_files(overrides_dir)
    if not files:
        print(f"No graphics in {overrides_dir} — skipping UI install.")
        print(f"  Drop edited .tga/.qda files under patch/overrides/Resource/...")
        return 0

    print(f"Installing {len(files)} graphic file(s) (may take 1-3 minutes)...")
    count = inject_files(pak, files)
    print(f"Installed {count} graphic file(s) from {overrides_dir}")
    for archive_path in sorted(files):
        print(f"  {decode_pak_path(archive_path)}")
    return count


def install_voices(game_dir: Path, voices_dir: Path) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    voice_files = collect_voice_files(voices_dir)
    if not voice_files:
        raise FileNotFoundError(f"No .ogg files found under {voices_dir}")

    count = inject_files(pak, voice_files)
    print(f"Installed {count} English voice files into resource0.pak")
    return count


def verify_game(game_dir: Path) -> None:
    exe = game_dir / "shveik.exe"
    pak = game_dir / "Resource" / "resource0.pak"
    if not exe.exists():
        raise FileNotFoundError(f"Missing game executable: {exe}")
    if not pak.exists():
        raise FileNotFoundError(f"Missing resource0.pak: {pak}")


def restore(game_dir: Path) -> None:
    pak = game_dir / "Resource" / "resource0.pak"
    if restore_backup(pak):
        print(f"Restored {pak} from backup.")
    else:
        print(f"No backup found at {pak}.original")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Subtitles only (English text, original Russian voices)
  python tools/install_patch.py --game-dir "C:/Games/Schweik"

  # Subtitles + English voice pack folder
  python tools/install_patch.py --game-dir "C:/Games/Schweik" --voices patch/voices_en

  # Restore original game data
  python tools/install_patch.py --game-dir "C:/Games/Schweik" --restore
        """,
    )
    parser.add_argument(
        "--game-dir",
        type=Path,
        default=DEFAULT_GAME,
        help="Path to the game folder containing shveik.exe",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "translation" / "schweik_dialogue.csv",
        help="Translation CSV with english column filled in",
    )
    parser.add_argument(
        "--btdb",
        type=Path,
        default=PATCH_DIR / "shveik_en.btdb",
        help="Pre-built English text database (skips CSV import)",
    )
    parser.add_argument(
        "--voices",
        type=Path,
        default=None,
        help="Folder of English .ogg files mirroring Resource/Voices/...",
    )
    parser.add_argument(
        "--ui-dir",
        type=Path,
        default=DEFAULT_OVERRIDES,
        help="Folder of edited graphics (mirror Resource/... paths). Default: patch/overrides/",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Install dialogue text only, skip graphics in --ui-dir",
    )
    parser.add_argument(
        "--graphics-only",
        action="store_true",
        help="Install graphics only, skip dialogue text",
    )
    parser.add_argument(
        "--no-cd",
        action="store_true",
        help="Merge resource1.pak into resource0.pak before patching",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore resource0.pak from backup",
    )
    args = parser.parse_args()

    if args.restore:
        restore(args.game_dir)
        return

    verify_game(args.game_dir)

    if args.no_cd:
        merge_cd_paks(args.game_dir)

    if args.graphics_only and args.text_only:
        raise SystemExit("Choose at most one of --text-only or --graphics-only.")

    if not args.graphics_only:
        prebuilt = args.btdb if args.btdb.exists() else None
        install_subtitles(args.game_dir, args.csv, prebuilt)

    if not args.text_only:
        install_graphics(args.game_dir, args.ui_dir)

    if args.voices:
        install_voices(args.game_dir, args.voices)

    print()
    print("Done. Launch the game in ScummVM (or shveik.exe).")
    if not args.voices:
        print("Voice mode: original Russian acting with English subtitles.")
    else:
        print("Voice mode: English voices installed.")


if __name__ == "__main__":
    main()