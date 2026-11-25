#!/usr/bin/env python3
"""Inject edited UI graphics back into resource0.pak."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.pak_paths import decode_pak_path
from tools.pak_utils import inject_files
from tools.scummvm_loose import collect_ui_files  # noqa: F401 — re-export for install_patch

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_UI_DIR = ROOT / "patch" / "ui_en"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--ui-dir", type=Path, default=DEFAULT_UI_DIR)
    args = parser.parse_args()

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    files = collect_ui_files(args.ui_dir)
    if not files:
        raise SystemExit(
            f"No .tga/.qda/.bmp files found in {args.ui_dir}. "
            "Keep the same folder layout as patch/ui_src/."
        )

    injected = inject_files(pak, files)
    print(f"Injected {injected} UI file(s) into {pak}")
    for archive_path in sorted(files):
        print(f"  {decode_pak_path(archive_path)}")


if __name__ == "__main__":
    main()