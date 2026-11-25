#!/usr/bin/env python3
"""Extract per-character voice samples for TTS cloning."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_CSV = ROOT / "translation" / "schweik_dialogue.csv"
DEFAULT_OUTPUT = ROOT / "translation" / "voice_samples"


def extract_samples(
    game_dir: Path,
    csv_path: Path,
    output_dir: Path,
    samples_per_character: int = 3,
) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise FileNotFoundError(f"Missing {pak}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Run export_text.py first. Missing {csv_path}")

    by_character: dict[str, list[str]] = defaultdict(list)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            voice_file = row.get("voice_file", "")
            character = row.get("character", "")
            if voice_file and character and voice_file not in by_character[character]:
                by_character[character].append(voice_file)

    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = 0

    with zipfile.ZipFile(pak, "r") as archive:
        members = set(archive.namelist())
        for character, voice_files in sorted(by_character.items()):
            char_dir = output_dir / character.replace("/", "_")
            char_dir.mkdir(parents=True, exist_ok=True)
            for voice_file in voice_files[:samples_per_character]:
                filename = Path(voice_file.replace("\\", "/")).name
                member = next(
                    (name for name in members if name.replace("\\", "/").endswith(filename)),
                    None,
                )
                if not member:
                    continue
                target = char_dir / filename
                target.write_bytes(archive.read(member))
                extracted += 1

    print(f"Extracted {extracted} samples for {len(by_character)} characters to {output_dir}")
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    extract_samples(args.game_dir, args.csv, args.output, args.samples)


if __name__ == "__main__":
    main()