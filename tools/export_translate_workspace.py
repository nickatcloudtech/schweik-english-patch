#!/usr/bin/env python3
"""Export every image asset that needs English translation into one folder.

Creates ``patch/to_translate/`` with PNGs for GIMP (letters, UI, scenes, map,
inventory, etc.) plus ``manifest.csv``. After editing:

  python3 tools/export_translate_workspace.py import
  ./deploy

Regenerate the workspace any time:

  python3 tools/export_translate_workspace.py export
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image

from tools.export_image_checklist import (
    DEFAULT_GAME,
    DEFAULT_LETTERS_PNG,
    DEFAULT_OVERRIDES,
    DEFAULT_OUTPUT as DEFAULT_CHECKLIST,
    DEFAULT_QDA_WORK,
    DEFAULT_UI_SRC,
    find_work_png,
    load_pak_index,
    resource_relative,
    retail_bytes,
)
from tools.pak_paths import decode_pak_path
from tools.qda_tools import parse_qda, pngs_to_qda, qda_to_pngs
from tools.tga_convert import ensure_engine_tga

DEFAULT_WORKSPACE = ROOT / "patch" / "to_translate"
DEFAULT_LETTERS_SRC = ROOT / "patch" / "letters" / "src"
DEFAULT_MANIFEST = DEFAULT_WORKSPACE / "manifest.csv"

# Map label sprites are few; keep them in the workspace even when already translated.
ALWAYS_INCLUDE_PREFIXES = ("Карта/",)

LETTER_CATEGORIES = frozenset(
    {
        "scene_closeup",
        "scene_document",
        "scene_journal",
        "scene_letter",
        "scene_prop",
        "scene_sign",
        "inventory_description_full",
        "inventory_description_short",
        "inventory_icon",
    }
)


def load_checklist(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def filter_rows(
    rows: list[dict[str, str]],
    *,
    include_translated: bool,
    priority: str,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in rows:
        if priority != "all" and row["priority"] != priority:
            continue
        if not include_translated and row["status"] == "translated":
            if not any(row["relative_path"].startswith(prefix) for prefix in ALWAYS_INCLUDE_PREFIXES):
                continue
        selected.append(row)
    return selected


def _png_stem(path: Path) -> str:
    name = path.name
    if "_f" in name and name.rsplit("_f", 1)[-1][:2].isdigit():
        return name.rsplit("_f", 1)[0]
    return path.stem


def related_pngs(work_png: Path) -> list[Path]:
    parent = work_png.parent
    stem = _png_stem(work_png)
    matches = sorted(parent.glob(f"{stem}*.png"))
    return matches or [work_png]


def export_qda_png(data: bytes, dest: Path) -> list[Path]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    animation = qda_to_pngs(data, dest)
    if len(animation.frames) == 1:
        return [dest]
    stem = dest.stem
    suffix = dest.suffix
    return [dest.with_name(f"{stem}_f{index:02d}{suffix}") for index in range(len(animation.frames))]


def export_tga_png(data: bytes, dest: Path, *, source_name: Path) -> list[Path]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    converted = ensure_engine_tga(data, source_name)
    Image.open(BytesIO(converted)).save(dest)
    return [dest]


def copy_png_set(source_files: list[Path], dest_base: Path) -> list[str]:
    written: list[str] = []
    for source in source_files:
        if len(source_files) == 1:
            target = dest_base
        else:
            target = dest_base.parent / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        written.append(str(target.relative_to(DEFAULT_WORKSPACE)))
    return written


def exact_work_png(rel: str, qda_work: Path, letters_png: Path) -> Path | None:
    rel_path = Path(rel)
    for root in (qda_work, letters_png):
        exact = (root / rel_path).with_suffix(".png")
        if exact.exists():
            return exact
    return None


def export_asset_png(
    row: dict[str, str],
    *,
    workspace: Path,
    qda_work: Path,
    letters_png: Path,
    ui_src: Path,
    pak_index: dict[str, bytes],
) -> tuple[list[str], str]:
    rel = row["relative_path"]
    rel_path = Path(rel)
    dest = (workspace / rel_path).with_suffix(".png")

    work_png = exact_work_png(rel, qda_work, letters_png) or find_work_png(rel, qda_work, letters_png)
    if work_png is not None:
        files = copy_png_set(related_pngs(work_png), dest)
        return files, "work_png"

    retail, source_kind = retail_bytes(row["archive_path"], pak_index, ui_src)
    if retail is None:
        raise FileNotFoundError(f"no retail source for {rel}")

    if rel_path.suffix.lower() == ".qda":
        files = [str(path.relative_to(workspace)) for path in export_qda_png(retail, dest)]
        return files, source_kind

    if rel_path.suffix.lower() == ".tga":
        files = [
            str(path.relative_to(workspace))
            for path in export_tga_png(retail, dest, source_name=ui_src / rel_path)
        ]
        return files, source_kind

    raise ValueError(f"unsupported format for {rel}")


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "index",
        "archive_path",
        "relative_path",
        "category",
        "priority",
        "status",
        "english_hint",
        "width",
        "height",
        "frames",
        "png_files",
        "export_source",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "index": str(index),
                    "archive_path": row.get("archive_path", f"Resource/{row['relative_path']}"),
                    "relative_path": row["relative_path"],
                    "category": row["category"],
                    "priority": row["priority"],
                    "status": row["status"],
                    "english_hint": row["english_hint"],
                    "width": row["width"],
                    "height": row["height"],
                    "frames": row["frames"],
                    "png_files": row.get("png_files", ""),
                    "export_source": row.get("export_source", ""),
                    "notes": row["notes"],
                }
            )


def write_readme(path: Path, *, asset_count: int, png_count: int) -> None:
    path.write_text(
        "\n".join(
            [
                "English translation workspace",
                "===========================",
                "",
                f"Assets: {asset_count}  |  PNG files: {png_count}",
                "",
                "Edit the PNGs here in GIMP or Krita.",
                "Do NOT change canvas size — only repaint the Russian text.",
                "",
                "Multi-frame animations use names like asset_f00.png, asset_f01.png.",
                "Edit every frame that contains text.",
                "",
                "When finished:",
                "  python3 tools/export_translate_workspace.py import",
                "  ./deploy",
                "",
                "See manifest.csv for hints (english_hint column) and dimensions.",
                "Regenerate after retail updates (keeps existing files unless --fresh):",
                "  python3 tools/export_translate_workspace.py export",
                "",
            ]
        ),
        encoding="utf-8",
    )


def cmd_export(args: argparse.Namespace) -> int:
    checklist_path = args.checklist
    if not checklist_path.exists():
        raise SystemExit(f"Missing {checklist_path} — run: python3 tools/export_image_checklist.py")

    pak = args.game_dir / "Resource" / "resource0.pak"
    if not pak.exists():
        raise SystemExit(f"Missing {pak}")

    rows = filter_rows(
        load_checklist(checklist_path),
        include_translated=args.include_translated,
        priority=args.priority,
    )
    if not rows:
        print("Nothing to export with current filters.")
        return 0

    if args.workspace.exists() and args.fresh:
        shutil.rmtree(args.workspace)
    args.workspace.mkdir(parents=True, exist_ok=True)

    pak_index = load_pak_index(pak)
    exported_rows: list[dict[str, str]] = []
    png_total = 0
    errors: list[str] = []

    for row in rows:
        try:
            png_files, export_source = export_asset_png(
                row,
                workspace=args.workspace,
                qda_work=args.qda_work,
                letters_png=args.letters_png,
                ui_src=args.ui_src,
                pak_index=pak_index,
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            errors.append(f"{row['relative_path']}: {exc}")
            continue

        row = dict(row)
        row["png_files"] = ";".join(png_files)
        row["export_source"] = export_source
        exported_rows.append(row)
        png_total += len(png_files)
        print(f"export {row['relative_path']} -> {png_files[0]}")

    write_manifest(args.manifest, exported_rows)
    write_readme(args.workspace / "README.txt", asset_count=len(exported_rows), png_count=png_total)

    print()
    print(f"Exported {len(exported_rows)} asset(s), {png_total} PNG file(s)")
    print(f"Workspace: {args.workspace}")
    print(f"Manifest:  {args.manifest}")

    if errors:
        print(f"\nSkipped {len(errors)} asset(s):")
        for error in errors[:20]:
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return 1
    return 0


def resolve_retail_qda(
    rel: str,
    *,
    ui_src: Path,
    letters_src: Path,
    pak_index: dict[str, bytes],
    archive_path: str,
) -> bytes:
    rel_path = Path(rel)
    for base in (ui_src / rel_path, letters_src / rel_path):
        if base.exists():
            return base.read_bytes()

    retail, _kind = retail_bytes(archive_path, pak_index, ui_src)
    if retail is not None and rel_path.suffix.lower() == ".qda":
        return retail
    raise FileNotFoundError(f"retail QDA not found for {rel}")


def png_to_engine_tga(png_path: Path, *, width: int, height: int) -> bytes:
    image = Image.open(png_path).convert("RGBA")
    if image.size != (width, height):
        print(
            f"warning: {png_path.name} is {image.size[0]}x{image.size[1]}, "
            f"resizing to {width}x{height} for TGA import"
        )
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="TGA")
    return ensure_engine_tga(buffer.getvalue(), png_path)


def tga_dimensions(data: bytes) -> tuple[int, int]:
    import struct

    if len(data) < 18:
        return 0, 0
    width, height = struct.unpack_from("<HH", data, 12)
    return width, height


def pack_png_path(workspace: Path, rel: str, frames: int) -> Path | None:
    rel_path = Path(rel)
    base = (workspace / rel_path).with_suffix(".png")
    if base.exists():
        return base
    if frames > 1:
        frame0 = base.with_name(f"{base.stem}_f00{base.suffix}")
        if frame0.exists():
            return frame0
    return None


def copy_workspace_pngs(workspace: Path, rel: str, dest_root: Path) -> list[Path]:
    rel_path = Path(rel)
    workspace_base = (workspace / rel_path).with_suffix(".png")
    copied: list[Path] = []
    for src in related_pngs(workspace_base):
        if not src.exists():
            continue
        if len(related_pngs(workspace_base)) == 1:
            target = (dest_root / rel_path).with_suffix(".png")
        else:
            target = dest_root / rel_path.parent / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)
    return copied


def cmd_import(args: argparse.Namespace) -> int:
    if not args.manifest.exists():
        raise SystemExit(f"Missing {args.manifest} — run export first")

    pak = args.game_dir / "Resource" / "resource0.pak"
    pak_index = load_pak_index(pak) if pak.exists() else {}

    with args.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    qda_count = 0
    tga_count = 0
    skipped = 0
    overrides_root = args.overrides / "Resource"
    overrides_root.mkdir(parents=True, exist_ok=True)

    for row in rows:
        rel = row["relative_path"]
        rel_path = Path(rel)
        frames = int(row["frames"] or "1")
        pack_png = pack_png_path(args.workspace, rel, frames)
        if pack_png is None:
            skipped += 1
            print(f"skip {rel} (no edited PNG in workspace)")
            continue

        copy_workspace_pngs(args.workspace, rel, args.qda_work)
        if row["category"] in LETTER_CATEGORIES:
            copy_workspace_pngs(args.workspace, rel, args.letters_png)

        if rel_path.suffix.lower() == ".qda":
            try:
                retail = resolve_retail_qda(
                    rel,
                    ui_src=args.ui_src,
                    letters_src=args.letters_src,
                    pak_index=pak_index,
                    archive_path=row.get("archive_path", f"Resource/{rel}"),
                )
            except FileNotFoundError as exc:
                print(f"skip {rel} ({exc})")
                skipped += 1
                continue

            target = overrides_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pngs_to_qda(retail, pack_png))
            qda_count += 1
            print(f"pack {pack_png.relative_to(args.workspace)} -> {target.relative_to(ROOT)}")
            continue

        if rel_path.suffix.lower() == ".tga":
            retail, _kind = retail_bytes(
                row.get("archive_path", f"Resource/{rel}"),
                pak_index,
                args.ui_src,
            )
            if retail is None:
                print(f"skip {rel} (retail TGA missing)")
                skipped += 1
                continue
            width, height = tga_dimensions(ensure_engine_tga(retail, rel_path))
            target = overrides_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(png_to_engine_tga(pack_png, width=width, height=height))
            tga_count += 1
            print(f"pack {pack_png.relative_to(args.workspace)} -> {target.relative_to(ROOT)}")

    print()
    print(f"Packed {qda_count} QDA(s) and {tga_count} TGA(s) into patch/overrides")
    if skipped:
        print(f"Skipped {skipped} asset(s) with no workspace PNG")

    if qda_count and args.run_deploy:
        print("Run ./deploy to copy overrides into the game folder.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--ui-src", type=Path, default=DEFAULT_UI_SRC)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--qda-work", type=Path, default=DEFAULT_QDA_WORK)
    parser.add_argument("--letters-png", type=Path, default=DEFAULT_LETTERS_PNG)
    parser.add_argument("--letters-src", type=Path, default=DEFAULT_LETTERS_SRC)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)

    sub = parser.add_subparsers(dest="cmd", required=True)

    export_parser = sub.add_parser("export", help="Build patch/to_translate/ from checklist")
    export_parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Also copy assets already marked translated (reference)",
    )
    export_parser.add_argument(
        "--priority",
        choices=("all", "required", "optional"),
        default="all",
        help="Export all non-translated assets (default), or filter by priority",
    )
    export_parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete existing workspace before export",
    )

    import_parser = sub.add_parser("import", help="Pack edited PNGs into patch/overrides")
    import_parser.add_argument(
        "--run-deploy",
        action="store_true",
        help="Remind to deploy (does not run deploy automatically)",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "export":
        raise SystemExit(cmd_export(args))
    if args.cmd == "import":
        raise SystemExit(cmd_import(args))
    raise SystemExit(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    main()