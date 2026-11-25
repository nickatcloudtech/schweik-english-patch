#!/usr/bin/env python3
"""Re-pack pristine cursor QDAs (fixes GIMP background / resize mistakes)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qda_tools import qda_to_pngs

DEFAULT_SRC = ROOT / "patch" / "ui_src" / "Resource" / "Animation"
DEFAULT_WORK = ROOT / "patch" / "qda_work" / "Animation"
DEFAULT_OUT = ROOT / "patch" / "overrides" / "Resource" / "Animation"


def restore_cursors(
    source: Path,
    work_dir: Path,
    output: Path,
    *,
    also_default_tga: bool,
) -> int:
    count = 0
    for qda_path in sorted(source.glob("курсор*.qda")):
        data = qda_path.read_bytes()
        png_path = (work_dir / qda_path.name).with_suffix(".png")
        qda_to_pngs(data, png_path)
        target = output / qda_path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        count += 1
        print(f"restored {qda_path.name} -> {target.relative_to(ROOT)}")

    if also_default_tga:
        tga_src = ROOT / "patch" / "ui_src" / "Resource" / "Cursors" / "default.tga"
        if tga_src.exists():
            from tools.tga_convert import ensure_engine_tga

            tga_out = ROOT / "patch" / "overrides" / "Resource" / "Cursors" / "default.tga"
            tga_out.parent.mkdir(parents=True, exist_ok=True)
            tga_out.write_bytes(ensure_engine_tga(tga_src.read_bytes(), tga_src))
            print(f"restored Cursors/default.tga -> {tga_out.relative_to(ROOT)}")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--default-tga", action="store_true", default=True)
    parser.add_argument("--no-default-tga", action="store_false", dest="default_tga")
    args = parser.parse_args()

    count = restore_cursors(
        args.source.resolve(),
        args.work.resolve(),
        args.output.resolve(),
        also_default_tga=args.default_tga,
    )
    print(f"Restored {count} cursor asset(s).")
    print("ScummVM: do NOT ./deploy cursors (Resource/Animation/ shadows the pak).")
    print("Inject into pak instead:")
    print("  python3 tools/install_patch.py --graphics-only --ui-dir patch/overrides")
    print("Or leave original cursors in the pak and skip cursor overrides.")


if __name__ == "__main__":
    main()