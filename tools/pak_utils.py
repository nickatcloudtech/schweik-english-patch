"""Helpers for reading and writing QD Engine .pak archives (ZIP files)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


def find_member(members: list[str], suffix: str) -> str | None:
    suffix_lower = suffix.replace("/", "\\").lower()
    for name in members:
        if name.replace("/", "\\").lower().endswith(suffix_lower):
            return name
    return None


def backup_file(path: Path) -> Path:
    backup = path.with_suffix(path.suffix + ".original")
    if not backup.exists():
        shutil.copy2(path, backup)
    return backup


def read_member(pak_path: Path, suffix: str) -> tuple[str, bytes]:
    with zipfile.ZipFile(pak_path, "r") as archive:
        member = find_member(archive.namelist(), suffix)
        if not member:
            raise FileNotFoundError(f"{suffix} not found in {pak_path}")
        return member, archive.read(member)


def replace_member(pak_path: Path, member_suffix: str, data: bytes) -> str:
    backup_file(pak_path)
    temp_path = pak_path.with_suffix(".tmp.pak")

    with zipfile.ZipFile(pak_path, "r") as src:
        member_names = src.namelist()
        target_member = find_member(member_names, member_suffix)
        if not target_member:
            raise FileNotFoundError(f"{member_suffix} not found in {pak_path}")

        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                if item.filename == target_member:
                    dst.writestr(item, data)
                else:
                    dst.writestr(item, src.read(item.filename))

    temp_path.replace(pak_path)
    return target_member


def _normalize_archive_path(path: str) -> str:
    return path.replace("/", "\\").lower()


def _match_file(files: dict[str, bytes], archive_name: str) -> tuple[str, bytes] | None:
    normalized_name = _normalize_archive_path(archive_name)
    for path, data in files.items():
        if _normalize_archive_path(path) == normalized_name:
            return path, data
    return None


def inject_files(pak_path: Path, files: dict[str, bytes]) -> int:
    """Inject or replace files in a pak. Keys are archive paths like Resource\\Voices\\...."""
    if not files:
        return 0

    backup_file(pak_path)
    temp_path = pak_path.with_suffix(".tmp.pak")
    injected = 0
    replaced_names: set[str] = set()

    with zipfile.ZipFile(pak_path, "r") as src:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                match = _match_file(files, item.filename)
                if match:
                    _, data = match
                    dst.writestr(item, data)
                    replaced_names.add(_normalize_archive_path(item.filename))
                    injected += 1
                else:
                    dst.writestr(item, src.read(item.filename))

            for archive_path, data in files.items():
                if _normalize_archive_path(archive_path) in replaced_names:
                    continue
                dst.writestr(archive_path, data)
                injected += 1

    temp_path.replace(pak_path)
    return injected


def collect_voice_files(voices_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in voices_dir.rglob("*.ogg"):
        relative = path.relative_to(voices_dir)
        archive_path = ("Resource\\Voices\\" + str(relative)).replace("/", "\\")
        files[archive_path] = path.read_bytes()
    return files


def restore_backup(pak_path: Path) -> bool:
    backup = pak_path.with_suffix(pak_path.suffix + ".original")
    if not backup.exists():
        return False
    shutil.copy2(backup, pak_path)
    return True