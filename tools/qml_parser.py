"""Parse QD Engine binary game scripts (.qml)."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

TAG_VOID = 0
TAG_SHORT = 1
TAG_UNSIGNED_SHORT = 2
TAG_INT = 3
TAG_UNSIGNED_INT = 4
TAG_FLOAT = 5
TAG_STRING = 6

QDSCR_NAME = 19
QDSCR_FILE = 11
QDSCR_TEXT = 29
QDSCR_SHORT_TEXT = 30
QDSCR_SOUND = 75
QDSCR_OBJECT_STATE = 108
QDSCR_TEXT_DB = 232

SCRIPT_MAGIC = 8383


@dataclass
class QmlTag:
    tag_id: int
    data_format: int
    data_size: int
    data_offset: int
    subtags: list[QmlTag] = field(default_factory=list)

    def data_string(self, pool: bytes) -> str:
        if self.data_format != TAG_STRING or self.data_size <= 0:
            return ""
        raw = pool[self.data_offset : self.data_offset + self.data_size]
        return raw.split(b"\x00", 1)[0].decode("cp1251", errors="replace")


@dataclass
class DialogueState:
    text_id: str
    sound_ref: str
    sound_file: str = ""


@dataclass
class VoiceMapping:
    text_id: str
    sound_files: list[str]
    sound_refs: list[str]
    states: list[DialogueState]


def read_tag(stream: bytes, offset: int) -> tuple[QmlTag, int]:
    tag_id, data_format, data_size, data_offset, num_subtags = struct.unpack_from("<5i", stream, offset)
    offset += 20
    tag = QmlTag(tag_id, data_format, data_size, data_offset, [])
    for _ in range(num_subtags):
        subtag, offset = read_tag(stream, offset)
        tag.subtags.append(subtag)
    return tag, offset


def load_binary_script(path: str | Path) -> tuple[bytes, QmlTag]:
    data = Path(path).read_bytes()
    magic, pool_size = struct.unpack_from("<2i", data, 0)
    if magic != SCRIPT_MAGIC:
        raise ValueError(f"Not a binary QD script (magic={magic})")
    pool = data[8 : 8 + pool_size]
    tag_data = data[8 + pool_size :]
    root, _ = read_tag(tag_data, 0)
    return pool, root


def _collect_sound_defs(tag: QmlTag, pool: bytes, sounds: dict[str, str]) -> None:
    if tag.tag_id == QDSCR_SOUND:
        name = ""
        file_name = ""
        for subtag in tag.subtags:
            if subtag.tag_id == QDSCR_NAME:
                name = subtag.data_string(pool)
            elif subtag.tag_id == QDSCR_FILE:
                file_name = subtag.data_string(pool)
        if name and file_name:
            sounds[name] = file_name.replace("/", "\\")

    for subtag in tag.subtags:
        _collect_sound_defs(subtag, pool, sounds)


def _collect_dialogue_states(
    tag: QmlTag,
    pool: bytes,
    sounds: dict[str, str],
    states: list[DialogueState],
) -> None:
    if tag.tag_id == QDSCR_OBJECT_STATE:
        text_id = ""
        sound_ref = ""
        for subtag in tag.subtags:
            if subtag.tag_id in (QDSCR_TEXT, QDSCR_SHORT_TEXT):
                value = subtag.data_string(pool)
                if value and not text_id:
                    text_id = value
            elif subtag.tag_id == QDSCR_SOUND:
                if subtag.data_format == TAG_STRING:
                    sound_ref = subtag.data_string(pool)
                else:
                    for child in subtag.subtags:
                        if child.tag_id == QDSCR_NAME:
                            sound_ref = child.data_string(pool)

        if text_id and sound_ref:
            states.append(
                DialogueState(
                    text_id=text_id,
                    sound_ref=sound_ref,
                    sound_file=sounds.get(sound_ref, ""),
                )
            )

    for subtag in tag.subtags:
        _collect_dialogue_states(subtag, pool, sounds, states)


def build_voice_index(states: list[DialogueState]) -> dict[str, VoiceMapping]:
    """Map btdb text_id -> all voiced script states that reference it."""
    grouped: dict[str, list[DialogueState]] = {}
    for state in states:
        if not state.sound_file:
            continue
        grouped.setdefault(state.text_id, []).append(state)

    index: dict[str, VoiceMapping] = {}
    for text_id, group in grouped.items():
        sound_files: list[str] = []
        sound_refs: list[str] = []
        seen: set[tuple[str, str]] = set()
        for state in group:
            key = (state.sound_ref, state.sound_file)
            if key in seen:
                continue
            seen.add(key)
            sound_refs.append(state.sound_ref)
            sound_files.append(state.sound_file)
        index[text_id] = VoiceMapping(
            text_id=text_id,
            sound_files=sound_files,
            sound_refs=sound_refs,
            states=group,
        )
    return index


def classify_unvoiced_text_id(text_id: str) -> str:
    if ".темы диалогов." in text_id:
        return "dialog topic label (no voice in game script)"
    if text_id.startswith("Прочие.") or ".Общие." in text_id:
        return "generic UI / narrator line (no voice in game script)"
    if text_id.startswith("ВРЕМЕННЫЕ."):
        return "unused/temp line (no voice in game script)"
    return "examine or subtitle-only line (no voice in game script)"


def match_voice_mapping(
    text_id: str,
    states: list[DialogueState],
    *,
    voice_index: dict[str, VoiceMapping] | None = None,
) -> VoiceMapping | None:
    """Link a .btdb row to voiced script state(s) by exact text_id."""
    index = voice_index or build_voice_index(states)
    return index.get(text_id)


def match_dialogue_state(
    text_id: str,
    russian: str,
    states: list[DialogueState],
    *,
    voice_index: dict[str, VoiceMapping] | None = None,
) -> DialogueState | None:
    mapping = match_voice_mapping(text_id, states, voice_index=voice_index)
    if not mapping:
        return None
    return mapping.states[0]


def format_voice_files(mapping: VoiceMapping | None) -> str:
    if not mapping:
        return ""
    return "|".join(mapping.sound_files)


def format_sound_refs(mapping: VoiceMapping | None) -> str:
    if not mapping:
        return ""
    return "|".join(mapping.sound_refs)


def parse_dialogue_mappings(path: str | Path) -> tuple[dict[str, str], list[DialogueState]]:
    pool, root = load_binary_script(path)
    sounds: dict[str, str] = {}
    states: list[DialogueState] = []
    _collect_sound_defs(root, pool, sounds)
    _collect_dialogue_states(root, pool, sounds, states)
    return sounds, states


def get_text_db_path(path: str | Path) -> str:
    pool, root = load_binary_script(path)

    def walk(tag: QmlTag) -> str:
        if tag.tag_id == QDSCR_TEXT_DB:
            return tag.data_string(pool)
        for subtag in tag.subtags:
            result = walk(subtag)
            if result:
                return result
        return ""

    return walk(root)