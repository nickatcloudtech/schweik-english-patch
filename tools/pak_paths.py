"""Decode QD Engine .pak (ZIP) member paths stored as CP1251."""

from __future__ import annotations


def decode_pak_path(name: str) -> str:
    """Return a Unicode archive path from the raw ZIP entry name."""
    try:
        return name.encode("cp437").decode("cp1251")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return name


def encode_pak_path(name: str) -> str:
    """Return the ZIP entry name used inside QD .pak archives."""
    return name.encode("cp1251").decode("cp437")