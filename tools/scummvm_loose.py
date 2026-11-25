"""ScummVM loose-file layout helpers for the QD Engine port.

ScummVM indexes the game directory with SearchMan.addDirectory(gamePath, 0, 4).
Only files up to four path components below the game folder are visible as loose
files. Deeper paths (e.g. Interface/Main menu/exit/*.qda) are ignored and the
engine falls back to resource0.pak.

See engines/engine.cpp initializePath() in the ScummVM qdengine tree.
"""

from __future__ import annotations

from pathlib import Path

# Directory levels below the game folder that SearchMan indexes.
SEARCHMAN_MAX_DEPTH = 4


def resource_path_depth(relative: Path) -> int:
    """Return path depth relative to the game folder (file name counts as one)."""
    return len(relative.parts)


def scummvm_loose_visible(relative: Path) -> bool:
    """True if ScummVM SearchMan can open this Resource-relative path loose."""
    return resource_path_depth(relative) <= SEARCHMAN_MAX_DEPTH


def collect_ui_files(ui_dir: Path) -> dict[str, bytes]:
    """Collect .tga/.qda/.bmp overrides keyed by pak archive paths."""
    files: dict[str, bytes] = {}
    allowed = {".tga", ".qda", ".bmp"}

    resource_root = ui_dir / "Resource"
    if resource_root.is_dir():
        scan_root = resource_root
        prefix = "Resource"
    else:
        scan_root = ui_dir
        prefix = ""

    for path in scan_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        if path.name == "manifest.csv":
            continue

        relative = path.relative_to(scan_root).as_posix()
        archive_path = f"{prefix}/{relative}" if prefix else relative
        files[archive_path.replace("/", "\\")] = path.read_bytes()

    return files


def is_interface_archive_path(archive_path: str) -> bool:
    return archive_path.replace("\\", "/").lower().startswith("resource/interface/")


def collect_pak_fallback_files(overrides_dir: Path) -> dict[str, bytes]:
    """Return nested Interface overrides ScummVM cannot see in SearchMan."""
    nested: dict[str, bytes] = {}
    for archive_path, data in collect_ui_files(overrides_dir).items():
        if not is_interface_archive_path(archive_path):
            continue
        relative = Path(archive_path.replace("\\", "/"))
        if not scummvm_loose_visible(relative):
            nested[archive_path] = data
    return nested


def interface_override_relatives(overrides_dir: Path) -> set[Path]:
    """Resource-relative Interface paths present in patch/overrides."""
    relatives: set[Path] = set()
    for archive_path in collect_ui_files(overrides_dir):
        if not is_interface_archive_path(archive_path):
            continue
        parts = Path(archive_path.replace("\\", "/")).parts
        if len(parts) >= 3 and parts[0].lower() == "resource" and parts[1].lower() == "interface":
            relatives.add(Path(*parts[2:]))
    return relatives