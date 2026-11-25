#!/usr/bin/env python3
"""Export QDA menu sprites to PNG for GIMP, then pack them back."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qda_tools import pngs_to_qda, qda_to_pngs

DEFAULT_UI = ROOT / "patch" / "ui_src"
DEFAULT_RESOURCE = DEFAULT_UI / "Resource"
DEFAULT_WORK = ROOT / "patch" / "qda_work"
MENU_SUBDIRS = ("Interface", "Inventory", "Экран смерти", "Animation")


def default_menu_sources() -> list[Path]:
    return [DEFAULT_RESOURCE / name for name in MENU_SUBDIRS if (DEFAULT_RESOURCE / name).exists()]


def iter_qda_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source.resolve()]
    return sorted(path.resolve() for path in source.rglob("*.qda"))


def resource_root_for(source: Path) -> Path:
    """Return the Resource/ folder that contains source QDAs."""
    source = source.resolve()
    resource = DEFAULT_RESOURCE.resolve()
    if source == resource or resource in source.parents:
        return resource
    if source.name == "Resource":
        return source
    raise ValueError(f"Could not find Resource root for {source}")


def qda_relative_path(qda_path: Path, *, resource_root: Path | None = None) -> Path:
    root = (resource_root or DEFAULT_RESOURCE).resolve()
    return qda_path.resolve().relative_to(root)


def export_qda(source: Path, work_dir: Path, *, resource_root: Path) -> tuple[int, int]:
    exported = 0
    skipped = 0
    root = resource_root.resolve()
    for qda_path in iter_qda_files(source):
        relative = qda_path.relative_to(root)
        png_path = (work_dir / relative).with_suffix(".png")
        try:
            qda_to_pngs(qda_path.read_bytes(), png_path)
        except (ValueError, FileNotFoundError) as exc:
            skipped += 1
            print(f"skip {relative} ({exc})")
            continue
        exported += 1
        print(f"export {relative} -> {png_path.relative_to(work_dir)}")
    return exported, skipped


def _pack_png_for_qda(work_dir: Path, qda_relative: Path) -> Path | None:
    png_path = (work_dir / qda_relative).with_suffix(".png")
    if png_path.exists():
        return png_path
    zones_png = work_dir / "zones" / png_path.name
    if zones_png.exists():
        return zones_png
    frame0 = png_path.with_name(f"{png_path.stem}_f00.png")
    if frame0.exists():
        return frame0
    startup_png = work_dir / "startup" / png_path.name
    if startup_png.exists():
        return startup_png
    return None


def import_qda(source: Path, work_dir: Path, output: Path) -> int:
    count = 0
    resource_root = resource_root_for(source)
    for qda_path in iter_qda_files(source):
        relative = qda_relative_path(qda_path, resource_root=resource_root)
        pack_png = _pack_png_for_qda(work_dir, relative)
        if pack_png is None:
            continue
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pngs_to_qda(qda_path.read_bytes(), pack_png))
        count += 1
        print(f"pack {pack_png.relative_to(work_dir)} -> {target.relative_to(output)}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    export_parser = sub.add_parser("export", help="QDA -> PNG for editing in GIMP")
    export_parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=None,
        help="Folder to export (default: Interface + Inventory + death screen). Repeatable.",
    )
    export_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)

    import_parser = sub.add_parser("import", help="PNG -> QDA after editing")
    import_parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_RESOURCE,
        help="Original QDA tree used as template when packing PNGs",
    )
    import_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    import_parser.add_argument("--output", type=Path, default=ROOT / "patch" / "overrides" / "Resource")

    args = parser.parse_args()
    if args.cmd == "export":
        sources = args.source or default_menu_sources()
        total_exported = 0
        total_skipped = 0
        for source in sources:
            source = (ROOT / source).resolve() if not source.is_absolute() else source.resolve()
            if not source.exists():
                print(f"skip missing source: {source}")
                continue
            print(f"Source: {source}")
            resource_root = resource_root_for(source)
            exported, skipped = export_qda(source, args.work, resource_root=resource_root)
            total_exported += exported
            total_skipped += skipped
        print(f"Exported {total_exported} PNG(s) to {args.work}")
        if total_skipped:
            print(f"Skipped {total_skipped} unsupported file(s).")
        print("Edit in GIMP/Krita (multi-frame cursors use *_f00.png, *_f01.png, ...).")
        print("Extract Russian labels: python3 tools/export_ui_text.py [--vision]")
        print("Then pack back: python3 tools/qda_edit.py import")
    else:
        source = args.source.resolve()
        count = import_qda(source, args.work.resolve(), args.output.resolve())
        print(f"Packed {count} QDA(s) to {args.output}")
        print("Then run: ./deploy")


if __name__ == "__main__":
    main()