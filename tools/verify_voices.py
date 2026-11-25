#!/usr/bin/env python3
"""Verify dialogue CSV voice paths against qd_game.qml script states."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.btdb import read_btdb_from_pak
from tools.qml_parser import (
    build_voice_index,
    format_voice_files,
    match_voice_mapping,
    parse_dialogue_mappings,
)

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_CSV = ROOT / "translation" / "schweik_dialogue.csv"


def verify(csv_path: Path, game_dir: Path) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    qml = game_dir / "qd_game.qml"
    entries = read_btdb_from_pak(pak)
    _, states = parse_dialogue_mappings(qml)
    voice_index = build_voice_index(states)

    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    rows = {row["id"]: row for row in csv_rows}

    missing_csv = 0
    wrong_csv = 0
    missing_btdb_voice = 0

    btdb_ids = {entry.text_id for entry in entries}
    for entry in entries:
        mapping = match_voice_mapping(entry.text_id, states, voice_index=voice_index)
        if not mapping:
            continue
        expected = format_voice_files(mapping)
        row = rows.get(entry.text_id)
        if not row:
            missing_csv += 1
            continue
        if (row.get("voice_file") or "").strip() != expected:
            wrong_csv += 1
            if wrong_csv <= 5:
                print(f"WRONG: {entry.text_id}")
                print(f"  csv:   {row.get('voice_file')}")
                print(f"  qml:   {expected}")

    for text_id in voice_index:
        if text_id not in btdb_ids:
            continue
        expected = format_voice_files(voice_index[text_id])
        row = rows.get(text_id)
        if row and not (row.get("voice_file") or "").strip():
            missing_btdb_voice += 1
            if missing_btdb_voice <= 5:
                print(f"MISSING voice_file in CSV for voiced line: {text_id}")

    print(f"Voiced script states: {len(voice_index)}")
    print(f"BTDB entries: {len(entries)}")
    print(f"CSV rows: {len(csv_rows)}")
    print(f"Voiced lines missing/incorrect in CSV: {wrong_csv + missing_btdb_voice}")
    print(f"Voiced lines missing from CSV entirely: {missing_csv}")

    problems = wrong_csv + missing_btdb_voice + missing_csv
    if problems:
        print("FAIL")
        return 1
    print("OK: every voiced script line has the correct voice_file in CSV")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    args = parser.parse_args()
    raise SystemExit(verify(args.csv, args.game_dir))


if __name__ == "__main__":
    main()