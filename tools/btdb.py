"""Read and write QD Engine binary text databases (.btdb)."""

from __future__ import annotations

import struct
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ENCODING = "cp1251"

# The retail game font/text DB uses CP1251. Fold common English diacritics to ASCII.
_ASCII_REPLACEMENTS = str.maketrans(
    {
        "Š": "S",
        "š": "s",
        "Ž": "Z",
        "ž": "z",
        "Č": "C",
        "č": "c",
        "Ř": "R",
        "ř": "r",
        "Ů": "U",
        "ů": "u",
        "Ě": "E",
        "ě": "e",
        "Ň": "N",
        "ň": "n",
        "Ď": "D",
        "ď": "d",
        "Ť": "T",
        "ť": "t",
        "Ü": "U",
        "ü": "u",
        "Ö": "O",
        "ö": "o",
        "Ä": "A",
        "ä": "a",
        "Á": "A",
        "á": "a",
        "É": "E",
        "é": "e",
        "Í": "I",
        "í": "i",
        "Ó": "O",
        "ó": "o",
        "Ú": "U",
        "ú": "u",
        "Ý": "Y",
        "ý": "y",
        "—": "-",
        "–": "-",
        "…": "...",
        "«": '"',
        "»": '"',
        "„": '"',
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
    }
)


def _clean(text: str) -> str:
    return text.replace("\x00", "").strip()


def to_cp1251_text(text: str) -> str:
    """Make text safe for the game's CP1251 .btdb encoding."""
    folded = text.translate(_ASCII_REPLACEMENTS)
    folded = unicodedata.normalize("NFKD", folded)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded.encode(ENCODING)  # fail fast while developing translations
    return folded


@dataclass
class TextEntry:
    text_id: str
    text: str
    sound: str = ""


def read_btdb(path: str | Path) -> list[TextEntry]:
    data = Path(path).read_bytes()
    offset = 0
    (count,) = struct.unpack_from("<i", data, offset)
    offset += 4

    entries: list[TextEntry] = []
    for _ in range(count):
        (id_len,) = struct.unpack_from("<i", data, offset)
        offset += 4
        text_id = _clean(data[offset : offset + id_len].decode(ENCODING))
        offset += id_len

        (txt_len,) = struct.unpack_from("<i", data, offset)
        offset += 4
        text = _clean(data[offset : offset + txt_len].decode(ENCODING))
        offset += txt_len

        (snd_len,) = struct.unpack_from("<i", data, offset)
        offset += 4
        sound = _clean(data[offset : offset + snd_len].decode(ENCODING, errors="replace"))
        offset += snd_len
        entries.append(TextEntry(text_id=text_id, text=text, sound=sound))

    return entries


def write_btdb(path: str | Path, entries: list[TextEntry]) -> None:
    parts = [struct.pack("<i", len(entries))]
    for entry in entries:
        text_id_b = entry.text_id.encode(ENCODING)
        text_b = entry.text.encode(ENCODING)
        sound_b = (entry.sound or "").encode(ENCODING)

        parts.append(struct.pack("<i", len(text_id_b)))
        parts.append(text_id_b)
        parts.append(struct.pack("<i", len(text_b)))
        parts.append(text_b)
        parts.append(struct.pack("<i", len(sound_b)))
        parts.append(sound_b)

    Path(path).write_bytes(b"".join(parts))


def read_btdb_from_pak(pak_path: str | Path, member: str = "Resource\\shveik.btdb") -> list[TextEntry]:
    import zipfile

    with zipfile.ZipFile(pak_path, "r") as archive:
        for name in archive.namelist():
            if name.lower().endswith("shveik.btdb") or name == member:
                return read_btdb_from_bytes(archive.read(name))
    raise FileNotFoundError(f"No .btdb found in {pak_path}")


def read_btdb_from_bytes(data: bytes) -> list[TextEntry]:
    offset = 0
    (count,) = struct.unpack_from("<i", data, offset)
    offset += 4
    entries: list[TextEntry] = []
    for _ in range(count):
        (id_len,) = struct.unpack_from("<i", data, offset)
        offset += 4
        text_id = _clean(data[offset : offset + id_len].decode(ENCODING))
        offset += id_len
        (txt_len,) = struct.unpack_from("<i", data, offset)
        offset += 4
        text = _clean(data[offset : offset + txt_len].decode(ENCODING))
        offset += txt_len
        (snd_len,) = struct.unpack_from("<i", data, offset)
        offset += 4
        sound = _clean(data[offset : offset + snd_len].decode(ENCODING, errors="replace"))
        offset += snd_len
        entries.append(TextEntry(text_id=text_id, text=text, sound=sound))
    return entries


def split_text_id(text_id: str) -> tuple[str, str, str]:
    parts = text_id.split(".", 2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return text_id, "", ""