#!/usr/bin/env python3
"""Fix inconsistent object state names in qd_game.qml for ScummVM.

Retail Schweik uses both ``отработан`` and ``отработано`` for the same
"animation sequence finished" state on controller objects. Scripts call
``is_state_active('отработан')``. Stock ScummVM warns when the object only
has ``отработано``; the original Windows game did not.

This performs a same-length in-place rename:
  отработано\\0  ->  отработан\\0\\0
leaving ``отработано закипание ...`` and other longer names untouched.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_QML = DEFAULT_GAME / "qd_game.qml"
DEFAULT_OUTPUT = ROOT / "patch" / "qd_game.qml"

OLD = "отработано".encode("cp1251") + b"\x00"
NEW = "отработан".encode("cp1251") + b"\x00\x00"


def patch_qml_states(data: bytes) -> tuple[bytes, int]:
    count = data.count(OLD)
    if not count:
        return data, 0
    return data.replace(OLD, NEW), count


def fix_qml_file(source: Path, output: Path) -> int:
    if not source.exists():
        raise FileNotFoundError(f"Missing {source}")

    data = source.read_bytes()
    patched, count = patch_qml_states(data)
    if count == 0:
        print(f"No standalone '{OLD[:-1].decode('cp1251')}' state names to fix in {source}")
        if source != output:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)
    print(f"Patched {count} state name(s): отработано -> отработан")
    print(f"Wrote {output}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_QML)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Patch --input file directly instead of writing --output",
    )
    args = parser.parse_args()

    output = args.input if args.in_place else args.output
    count = fix_qml_file(args.input, output)
    if count == 0 and not args.in_place and not output.exists():
        raise SystemExit(1)


if __name__ == "__main__":
    main()