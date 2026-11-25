#!/usr/bin/env python3
"""Import translated CSV into an English .btdb text database."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.btdb import TextEntry, read_btdb_from_pak, to_cp1251_text, write_btdb

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_INPUT = ROOT / "translation" / "schweik_dialogue.csv"
DEFAULT_OUTPUT = ROOT / "patch" / "shveik_en.btdb"


def import_dialogue(
    csv_path: Path,
    game_dir: Path,
    output_path: Path,
    fallback_to_russian: bool = True,
) -> int:
    pak = game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise FileNotFoundError(f"Missing {pak}")

    translations: dict[str, dict[str, str]] = {}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            translations[row["id"]] = row

    entries = read_btdb_from_pak(pak)
    english_entries: list[TextEntry] = []
    translated_count = 0

    for entry in entries:
        row = translations.get(entry.text_id, {})
        english = (row.get("english") or "").strip()
        if english:
            translated_count += 1
            english_entries.append(
                TextEntry(
                    text_id=entry.text_id,
                    text=to_cp1251_text(english),
                    sound=entry.sound,
                )
            )
        elif fallback_to_russian:
            english_entries.append(entry)
        else:
            english_entries.append(TextEntry(text_id=entry.text_id, text="", sound=entry.sound))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_btdb(output_path, english_entries)
    print(f"Wrote {output_path}")
    print(f"Translated lines: {translated_count}/{len(entries)}")
    return translated_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Leave untranslated lines empty instead of keeping Russian text",
    )
    args = parser.parse_args()
    import_dialogue(args.input, args.game_dir, args.output, fallback_to_russian=not args.no_fallback)


if __name__ == "__main__":
    main()