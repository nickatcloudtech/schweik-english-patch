# Schweik English Localization — Project TODO

Open-source fan translation of *The Adventures of the Good Soldier Schweik* (Похождения бравого солдата Швейка, 2007) for the QD Engine.

## Phase 1: Subtitles + Original Voices (launch target)

**No recompile required** — patch installs into `resource0.pak` via `tools/install_patch.py`.

- [x] Extract game from CD images
- [x] No-CD patch (merge `resource1.pak` into `resource0.pak`)
- [x] Export dialogue CSV (`tools/export_text.py` → `translation/schweik_dialogue.csv`)
- [x] Patch installer (`tools/install_patch.py`) — see `INSTALL.md`
- [x] Voice injection tool (`tools/inject_voices.py`)
- [x] **Translate all 4,434 dialogue lines** (`translation/schweik_dialogue.csv` → `english` column) — version 0.9.0
- [x] Build `patch/shveik_en.btdb`
- [ ] End-to-end playthrough test on Windows with retail `shveik.exe`
- [ ] GitHub release: patch + tools + INSTALL.md

## Phase 2: English Voice Pack (optional, for a contributor)

Not planned for 1.0. The original Russian performances stay. The file map is ready for someone else to record. See the README section "Why there is no English dub".

- [ ] Define voice profile per character (~20 roles, see CD README credits)
- [ ] Extract reference samples (`python3 tools/extract_voices.py`)
- [ ] Generate ~4,157 English OGG files into `patch/voices_en/` (same filenames as original)
- [ ] QA pass: timing, tone, mispronunciations
- [ ] Ship as separate download; install with `--voices patch/voices_en`

## Phase 3: Polish & Community

- [ ] Contributor guide for translators and voice reviewers (see `INSTALL.md`)
- [ ] Credit original Russian voice cast in release notes
- [ ] GitHub release with patch + optional voice pack

## Install modes (chosen at patch time, no in-game menu)

| Install command | Text | Audio |
|-----------------|------|-------|
| `install_patch.py` | English | Original Russian |
| `install_patch.py --voices patch/voices_en` | English | English OGGs |
| `install_patch.py --restore` | Russian | Original Russian |

## Tools

| Script | Purpose |
|--------|---------|
| `tools/extract_schweik.py` | Extract game from CD `.mdf` images |
| `tools/nocd_patch.py` | Merge CD resources for no-disc play |
| `tools/export_text.py` | Export dialogue CSV for translators |
| `tools/import_text.py` | Build `shveik_en.btdb` from translated CSV |
| `tools/extract_voices.py` | Pull per-character OGG samples for TTS |
| `tools/install_patch.py` | **Main installer** — patches resource0.pak in place |
| `tools/inject_voices.py` | Add/update English voice OGGs |

## Translation workflow

1. Run `python3 tools/export_text.py`
2. Edit `translation/schweik_dialogue.csv` — fill the `english` column
3. Run `python3 tools/import_text.py` → `patch/shveik_en.btdb`
4. Run `python3 tools/install_patch.py --game-dir <path> --no-cd`