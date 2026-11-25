#!/usr/bin/env python3
"""Refresh voice_file/sound_ref columns in an existing dialogue CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qml_parser import (
    build_voice_index,
    classify_unvoiced_text_id,
    format_sound_refs,
    format_voice_files,
    match_voice_mapping,
    parse_dialogue_mappings,
)

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_CSV = ROOT / "translation" / "schweik_dialogue.csv"


def refresh_voice_columns(csv_path: Path, game_dir: Path) -> tuple[int, int, int]:
    qml = game_dir / "qd_game.qml"
    if not qml.exists():
        raise FileNotFoundError(f"Missing {qml}")

    _, states = parse_dialogue_mappings(qml)
    voice_index = build_voice_index(states)

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []

    if "voice_file" not in fieldnames:
        fieldnames.append("voice_file")
    if "sound_ref" not in fieldnames:
        fieldnames.append("sound_ref")
    if "notes" not in fieldnames:
        fieldnames.append("notes")

    updated = 0
    voiced = 0
    subtitle_only = 0
    for row in rows:
        text_id = row["id"]
        mapping = match_voice_mapping(text_id, states, voice_index=voice_index)
        new_voice = format_voice_files(mapping)
        new_ref = format_sound_refs(mapping)
        if mapping:
            voiced += 1
            new_notes = ""
            if len(mapping.sound_files) > 1:
                new_notes = (
                    "short line id reused with multiple voice files; "
                    "pipe-separated list is complete"
                )
        else:
            subtitle_only += 1
            new_notes = classify_unvoiced_text_id(text_id)

        if (
            row.get("voice_file", "") != new_voice
            or row.get("sound_ref", "") != new_ref
            or row.get("notes", "") != new_notes
        ):
            updated += 1

        row["voice_file"] = new_voice
        row["sound_ref"] = new_ref
        row["notes"] = new_notes

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return updated, voiced, subtitle_only


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    args = parser.parse_args()

    updated, voiced, subtitle_only = refresh_voice_columns(args.csv, args.game_dir)
    print(f"Updated {updated} row(s) in {args.csv}")
    print(f"Voiced rows: {voiced}")
    print(f"Subtitle-only rows: {subtitle_only}")


if __name__ == "__main__":
    main()