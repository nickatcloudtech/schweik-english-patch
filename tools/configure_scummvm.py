#!/usr/bin/env python3
"""Relabel an existing Schweik ScummVM entry as English (display only).

Stock ScummVM only detects shveik as Russian (target id shveik-ru).
Do not change the ``language`` ini key — ScummVM uses it when re-identifying
the game on launch and will fail with language=en.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = ROOT / "game" / "shveik" / "app"

ENGLISH_DESCRIPTION = (
    "The Adventures of the Good Soldier Schweik (Windows/English)"
)
TARGET_SECTION = "shveik-ru"
LEGACY_EN_SECTION = "shveik-en"


def scummvm_ini_paths() -> list[Path]:
    candidates: list[Path] = []
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidates.append(Path(xdg) / "scummvm" / "scummvm.ini")
    candidates.append(Path.home() / ".config" / "scummvm" / "scummvm.ini")
    candidates.append(
        Path.home() / "snap" / "scummvm" / "current" / ".config" / "scummvm" / "scummvm.ini"
    )

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path.expanduser())
    return unique


def normalize_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def parse_ini(text: str) -> tuple[dict[str, dict[str, str]], list[str]]:
    sections: dict[str, dict[str, str]] = {}
    order: list[str] = []
    current: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            sections.setdefault(current, {})
            if current not in order:
                order.append(current)
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        sections[current][key.strip()] = value.strip()

    return sections, order


def serialize_ini(sections: dict[str, dict[str, str]], order: list[str]) -> str:
    lines: list[str] = []
    for section in order:
        lines.append(f"[{section}]")
        for key, value in sections[section].items():
            lines.append(f"{key}={value}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def find_shveik_section(
    sections: dict[str, dict[str, str]],
    game_dir: Path,
) -> str | None:
    target = normalize_path(game_dir)
    for name, values in sections.items():
        if values.get("gameid") != "shveik":
            continue
        if values.get("path") and normalize_path(Path(values["path"])) == target:
            return name
    return None


def configure_ini_text(text: str, game_dir: Path) -> tuple[str, bool]:
    sections, order = parse_ini(text)
    source_section = find_shveik_section(sections, game_dir)
    if not source_section:
        return text, False

    values = dict(sections[source_section])
    values["description"] = ENGLISH_DESCRIPTION
    values["language"] = "ru"
    values["path"] = normalize_path(game_dir)
    values.setdefault("platform", "windows")
    values.setdefault("gameid", "shveik")
    values.setdefault("engineid", "qdengine")
    values["guioptions"] = "lang_Russian plat_windows"

    if source_section != TARGET_SECTION:
        sections.pop(source_section, None)
        if source_section in order:
            order.remove(source_section)
        sections[TARGET_SECTION] = values
        if TARGET_SECTION not in order:
            order.append(TARGET_SECTION)
    else:
        sections[TARGET_SECTION] = values

    if LEGACY_EN_SECTION in sections:
        sections.pop(LEGACY_EN_SECTION, None)
        if LEGACY_EN_SECTION in order:
            order.remove(LEGACY_EN_SECTION)

    scummvm = sections.setdefault("scummvm", {})
    if "scummvm" not in order:
        order.insert(0, "scummvm")
    scummvm["lastselectedgame"] = TARGET_SECTION

    return serialize_ini(sections, order), True


def configure_scummvm(game_dir: Path, *, ini_path: Path | None = None) -> Path | None:
    candidates = [ini_path] if ini_path else scummvm_ini_paths()
    for path in candidates:
        if path is None or not path.exists():
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated, changed = configure_ini_text(original, game_dir)
        if not changed:
            continue
        path.write_text(updated, encoding="utf-8")
        return path
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--ini", type=Path, default=None, help="Explicit scummvm.ini path")
    args = parser.parse_args()

    if not args.game_dir.exists():
        raise SystemExit(f"Game folder not found: {args.game_dir}")

    updated = configure_scummvm(args.game_dir.resolve(), ini_path=args.ini)
    if updated:
        print(f"Updated ScummVM config: {updated}")
        print(f"  target: {TARGET_SECTION}")
        print(f"  description: {ENGLISH_DESCRIPTION}")
        print("  language: ru (required for stock ScummVM detection)")
    else:
        print("No ScummVM game entry found for this folder.")
        print("Add the game in ScummVM first, then run ./deploy again.")


if __name__ == "__main__":
    main()