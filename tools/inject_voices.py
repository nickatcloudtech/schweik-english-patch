#!/usr/bin/env python3
"""
Inject or update English voice files into the game's resource0.pak.

Folder layout mirrors the in-game paths after Resource/Voices/:

  voices/
    Комната Швейка/
      ep01_001.ogg
    Кац/
      ep02_045.ogg

Or use full paths from the CSV voice_file column:

  voices/
    Resource/Voices/Комната Швейка/ep01_001.ogg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pak_utils import collect_voice_files, inject_files

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"


def collect_voice_files_flexible(voices_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    for path in voices_dir.rglob("*.ogg"):
        relative = path.relative_to(voices_dir).as_posix()
        if relative.lower().startswith("resource/voices/"):
            archive_path = relative.replace("/", "\\")
        else:
            archive_path = ("Resource\\Voices\\" + relative).replace("/", "\\")
        files[archive_path] = path.read_bytes()

    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--voices-dir", type=Path, required=True)
    args = parser.parse_args()

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    files = collect_voice_files_flexible(args.voices_dir)
    if not files:
        raise SystemExit(f"No .ogg files found in {args.voices_dir}")

    count = inject_files(pak, files)
    print(f"Injected {count} voice files into {pak}")


if __name__ == "__main__":
    main()