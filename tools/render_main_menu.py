#!/usr/bin/env python3
"""Composite the main menu from deployed assets (sanity check for art)."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image

from tools.qda_tools import decode_rle_frame, parse_qda
from tools.tga_convert import ensure_engine_tga

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OVERRIDES = ROOT / "patch" / "overrides"
DEFAULT_OUT = ROOT / "patch" / "main_menu_composite.png"

BUTTONS = (
    ("new game", "new_active.qda", (400, 300)),
    ("load", "load_active.qda", (400, 300)),
    ("save", "save_active.qda", (400, 300)),
    ("resume", "resume_active.qda", (400, 300)),
    ("exit", "exit_active.qda", (400, 300)),
)

SLIDERS = (
    ("music.qda", (141, 576)),
    ("zvuk.qda", (659, 576)),
)


def load_tga(path: Path) -> Image.Image:
    data = ensure_engine_tga(path.read_bytes(), path)
    header = data[:18]
    width, height = struct.unpack_from("<HH", header, 12)
    bpp = header[16]
    offset = 18 + header[0]
    channels = bpp // 8
    return Image.frombytes("RGBA", (width, height), data[offset : offset + width * height * channels])


def paste_qda(canvas: Image.Image, qda_path: Path, center: tuple[int, int]) -> None:
    frame = parse_qda(qda_path.read_bytes()).frames[0]
    sprite = decode_rle_frame(frame)
    cx, cy = center
    x = cx - frame.canvas_w // 2 + frame.offset_x
    y = cy - frame.canvas_h // 2 + frame.offset_y
    canvas.alpha_composite(sprite, (x, y))


def _qda_source(game_dir: Path, overrides_dir: Path, folder: str, filename: str) -> Path:
    loose = game_dir / "Resource" / "Interface" / "Main menu" / folder / filename
    if loose.exists():
        return loose
    override = overrides_dir / "Resource" / "Interface" / "Main menu" / folder / filename
    if override.exists():
        return override
    raise FileNotFoundError(loose)


def render(game_dir: Path, output: Path, *, overrides_dir: Path = DEFAULT_OVERRIDES) -> Path:
    menu = game_dir / "Resource" / "Interface" / "Main menu"
    canvas = load_tga(menu / "fon.tga").convert("RGBA")
    for folder, filename, pos in BUTTONS:
        paste_qda(canvas, _qda_source(game_dir, overrides_dir, folder, filename), pos)
    for filename, pos in SLIDERS:
        paste_qda(canvas, menu / filename, pos)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = render(args.game_dir.resolve(), args.output.resolve())
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()