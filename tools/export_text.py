#!/usr/bin/env python3
"""Export Schweik dialogue to CSV for community translation."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.btdb import read_btdb_from_pak, split_text_id
from tools.qml_parser import (
    build_voice_index,
    classify_unvoiced_text_id,
    format_sound_refs,
    format_voice_files,
    match_voice_mapping,
    parse_dialogue_mappings,
)

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OUTPUT = ROOT / "translation" / "schweik_dialogue.csv"


def resolve_paths(game_dir: Path) -> tuple[Path, Path]:
    pak = game_dir / "Resource" / "resource0.pak"
    qml = game_dir / "qd_game.qml"
    if not pak.exists():
        raise FileNotFoundError(f"Missing {pak}")
    if not qml.exists():
        raise FileNotFoundError(f"Missing {qml}")
    return pak, qml


def export_dialogue(game_dir: Path, output: Path) -> int:
    pak, qml = resolve_paths(game_dir)
    entries = read_btdb_from_pak(pak)
    _, states = parse_dialogue_mappings(qml)
    voice_index = build_voice_index(states)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "location",
                "character",
                "russian",
                "english",
                "voice_file",
                "sound_ref",
                "notes",
            ],
        )
        writer.writeheader()

        mapped = 0
        subtitle_only = 0
        for entry in entries:
            location, character, _ = split_text_id(entry.text_id)
            mapping = match_voice_mapping(entry.text_id, states, voice_index=voice_index)
            if mapping:
                mapped += 1
                notes = ""
                if len(mapping.sound_files) > 1:
                    notes = (
                        "short line id reused with multiple voice files; "
                        "pipe-separated list is complete"
                    )
            else:
                subtitle_only += 1
                notes = classify_unvoiced_text_id(entry.text_id)
            writer.writerow(
                {
                    "id": entry.text_id,
                    "location": location,
                    "character": character,
                    "russian": entry.text,
                    "english": "",
                    "voice_file": format_voice_files(mapping),
                    "sound_ref": format_sound_refs(mapping),
                    "notes": notes,
                }
            )

    print(f"Exported {len(entries)} lines to {output}")
    print(
        f"Voice mappings: {mapped}/{len(entries)} lines linked to "
        f"{len(voice_index)} unique voiced script states"
    )
    print(f"Subtitle-only lines: {subtitle_only} (empty voice_file is expected for these)")
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export_dialogue(args.game_dir, args.output)


if __name__ == "__main__":
    main()