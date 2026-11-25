# Localization & contribution guide

How to fork this project, add languages, dub voices, translate UI graphics, and ship a playable patch.

**Last updated:** 2026-07-07 — in-game map (`Resource/Карта`) extraction workflow documented.

> **Maintainers:** update this file whenever tools, deploy paths, CSV columns, engine localization hooks, or ScummVM workarounds change. This is the single source of truth for “how to add languages / voices / UI.”

---

## Table of contents

1. [What you need](#what-you-need)
2. [Fork & quick start](#fork--quick-start)
3. [Repository layout](#repository-layout-translation-work)
4. [Dialogue translation](#dialogue-translation)
5. [Adding another language](#adding-another-language-german-french-)
6. [Voices](#voices)
7. [UI graphics](#ui-graphics-menus-buttons-startup-quote)
8. [In-game map](#in-game-map-resourceкарта)
9. [Deploy & install](#deploy--install-methods)
10. [Verification checklist](#verification-checklist)
11. [Tool reference](#tool-reference)
12. [Troubleshooting](#troubleshooting)
13. [Contributing back](#contributing-back)

---

## What you need

| Requirement | Notes |
|-------------|--------|
| Legal copy of *The Adventures of the Good Soldier Schweik* | CDs or your own install folder |
| Python 3.10+ | All patch tools |
| Pillow | `pip install pillow` — UI sprite export/import |
| Game folder | `qd_game.qml`, `shveik.exe`, `Resource/resource0.pak` |
| (Optional) ScummVM | Recommended player; see [INSTALL.md](../INSTALL.md) |
| (Optional) GIMP/Krita | UI graphics (QDA → PNG round-trip) |
| (Optional) Ollama | Batch dialogue translation via `translate_ollama.py` |

This repo ships **tools and translations only** — never commit retail game assets (`resource0.pak`, `shveik.exe`, etc.). See `.gitignore`.

---

## Fork & quick start

### Players (English subtitles + Russian voices)

```bash
git clone https://github.com/YOUR_USER/qdEngine.git
cd qdEngine

# Put your game in game/shveik/app/  (or pass path to ./deploy later)
pip install pillow
./deploy
```

Restart ScummVM fully after each `./deploy`.

### Contributors (your own language fork)

```bash
git clone https://github.com/YOUR_USER/qdEngine.git
cd qdEngine
git checkout -b localization/german   # example

# 1. Point at your legal game install
export GAME=/path/to/Schweik   # or use game/shveik/app/

# 2. Dialogue — fill your language column in the CSV (see below)
python3 tools/import_text.py --game-dir "$GAME"
python3 tools/fix_voice_paths.py && python3 tools/verify_voices.py

# 3. UI (optional) — export PNGs, edit, re-import
python3 tools/qda_edit.py export
# ... edit patch/qda_work/ ...
python3 tools/qda_edit.py import

# 4. Voices (optional) — record dubs, place under patch/voices_<lang>/
# 5. Ship
./deploy "$GAME"
```

### What `./deploy` does

- Builds `patch/shveik_en.btdb` from `translation/schweik_dialogue.csv` if the CSV is newer
- Copies text DB to `Resource/shveik_en.btdb` **and** `Resource/shveik.btdb` (ScummVM loose override)
- Copies UI overrides from `patch/overrides/Resource/`
- Installs all 255 top-level `Resource/Animation/` QDAs (full set referenced by `qd_game.qml`)
- Installs full `Resource/Инвентарь/` (~238 files) — inventory item icons, letters, examine screens (Cyrillic pak paths fail in ScummVM)
- Installs full `Resource/Sound/` and `Resource/Music/` on every deploy
- Installs full `Resource/Interface/` or `Resource/Inventory/` when UI overrides touch those folders
- Installs full `Resource/<room>/` for any room with UI overrides (map, startup quote, death screen, etc.)
- Writes `qd_game.ini` with `language=english`, `voice_mode=original`
- Deploys `patch/qd_game.qml` (fixes inconsistent `отработан` / `отработано` state names for ScummVM)
- Drops `scummvm_english.marker` and `readme_en.txt` for optional custom ScummVM detection
- Relabels your ScummVM library entry as **Windows/English** (keeps detection id `shveik-ru`)

---

## Repository layout (translation work)

```
translation/
  schweik_dialogue.csv     # Master dialogue DB (4,434 rows)
  ui_strings.csv           # Optional UI label helper
  voice_samples/           # Extracted reference clips (generated)

patch/
  shveik_en.btdb           # Built English text database
  qd_game.ini              # In-game language / voice_mode template
  overrides/Resource/      # Loose English UI files (QDA, TGA)
  ui_src/Resource/         # Extracted Russian UI sources (extract_ui.py)
  qda_work/                # PNG edit workspace (qda_edit.py)
  resource_loose/          # Full Resource/<folder>/ trees for ScummVM (generated, gitignored)
  letters/                 # Letter/document extraction workspace (extract_letters.py)
  voices_en/               # English .ogg dub (optional)
  scummvm_english.marker   # Optional ScummVM detection marker
  readme_en.txt            # In-game readme for English patch
  qd_game.qml              # Patched game script (state-name fix for ScummVM)

tools/                     # Python utilities (see table below)
game/shveik/app/           # Your game install (gitignored)
src/QD/Core/qdCore/        # qd_localization.* engine hooks
scummvm/                   # Optional upstream detection patch
```

---

## Dialogue translation

### CSV format (`translation/schweik_dialogue.csv`)

| Column | Purpose |
|--------|---------|
| `id` | Unique text id from `shveik.btdb` (**do not rename**) |
| `location` | Scene / room hint for translators |
| `character` | Speaker name |
| `russian` | Original Russian line |
| `english` | Translation column (today: English; add `german`, etc. for other langs) |
| `voice_file` | Path(s) to original `.ogg` in `Resource/Voices/` (pipe-separated if reused) |
| `sound_ref` | Short sound id from `qd_game.qml` |
| `notes` | Examine-only lines, mapping quirks, etc. |

**Coverage (English patch):** 4,434 lines total · 3,946 voiced · 488 subtitle/examine-only (no voice in original script).

### Workflow

```bash
# 1. Export fresh CSV from your game (only if you need to reset or re-sync ids)
python3 tools/export_text.py --game-dir /path/to/game

# 2. Edit translation/schweik_dialogue.csv
#    Fill the target language column (today: english)

# 3. Build text database
python3 tools/import_text.py
#    Writes patch/shveik_en.btdb

# 4. Refresh & verify voice mapping columns
python3 tools/fix_voice_paths.py
python3 tools/verify_voices.py

# 5. Install
./deploy
```

### Batch translate with Ollama (optional)

```bash
# Fill empty english cells using a local model
python3 tools/translate_ollama.py --model llama3.1
# Then review CSV manually — humor/satire needs human pass
python3 tools/import_text.py && ./deploy
```

### Import options

```bash
python3 tools/import_text.py --input translation/schweik_dialogue.csv
python3 tools/import_text.py --no-fallback   # untranslated lines become empty, not Russian
python3 tools/import_text.py --output patch/shveik_en.btdb --game-dir /path/to/game
```

By default, untranslated rows keep the original Russian text in the output btdb (`--no-fallback` disables this).

**Never hand-edit `.btdb` files** — always rebuild with `import_text.py`.

---

## Adding another language (German, French, …)

Today the engine and tools are **English-first**. English is fully wired; other languages need small extensions (or a pragmatic workaround).

### Option A — No code changes (fastest)

Ship your translation by reusing the English pipeline:

| Approach | Steps |
|----------|-------|
| **Reuse `english` column** | Put German/French text in the `english` column (name is historical). `import_text.py` → `./deploy`. |
| **Overwrite primary btdb** | Deploy copies the same btdb to both `shveik.btdb` and `shveik_en.btdb`. ScummVM loads loose `shveik.btdb` even without engine `_en` suffix logic. |
| **Ini language** | Keep `language=english` in `patch/qd_game.ini` for now (engine only knows `russian` / `english`). |

Good for a one-language community fork. Document your real language in the fork README.

### Option B — Proper multi-language support (recommended for long-term forks)

1. **CSV** — Add a column per language, e.g. `german`, `french`.

2. **`tools/import_text.py`** — Extend with `--column german --output patch/shveik_de.btdb` (today hard-codes `english`).

3. **`tools/deploy_loose.py`** — Deploy the matching btdb; generalize `DEFAULT_BTDB` / copy names:
   ```ini
   [localization]
   language=english    # extend engine for german, etc.
   voice_mode=original
   ```
   For stock ScummVM, also copy your btdb to `Resource/shveik.btdb` so subtitles load without custom engine builds.

4. **Engine (`src/QD/Core/qdCore/qd_localization.*`)** — Today only `russian` / `english` in `qd_game.ini`:
   - Extend `Language` enum and `language_name()` / `load()` parsing
   - Generalize `resolve_text_database()` — currently inserts `_en` before `.btdb` (`shveik.btdb` → `shveik_en.btdb`)
   - Pattern for new langs: `shveik_de.btdb`, `shveik_fr.btdb`, etc.

5. **Voices** — Generalize `translate_resource_path()`:
   - Today: `Resource/Voices/` → `Resource/Voices_en/` when `voice_mode=translated`
   - Add `Resource/Voices_de/`, etc., or `patch/voices_<lang>/`

6. **ScummVM** — Stock builds only detect `shveik-ru`. Optional: apply `scummvm/shveik_english_detection.patch` and add per-language markers (same pattern as `scummvm_english.marker`).

7. **Document** your language code in this file and update the tool table.

### Language fork checklist

- [ ] CSV column filled and reviewed
- [ ] `import_text.py` extended (or `english` column reused)
- [ ] `patch/qd_game.ini` updated if engine supports your language code
- [ ] UI graphics translated (`qda_edit.py`) if you want localized menus
- [ ] Voice pack under `patch/voices_<lang>/` (optional)
- [ ] `./deploy` tested in ScummVM
- [ ] This file updated with your language code and any new tool flags

---

## Voices

Original Russian voice acting lives in `Resource/Voices/` inside `resource0.pak`. Paths come from **`qd_game.qml` script states**, not the `sound` field in `shveik.btdb` (always empty in retail).

### Voice modes (`patch/qd_game.ini`)

| `voice_mode` | Behavior |
|--------------|----------|
| `original` | Russian voices + translated subtitles (**default**) |
| `translated` | Engine loads `Resource/Voices_en/` instead of `Resource/Voices/` (needs `qd_localization` in your runtime; stock ScummVM upstream may not include this yet) |
| `subtitles_only` | No voice playback |

### Two ways to install dubbed audio

| Method | Target path in game | `voice_mode` | Works on |
|--------|---------------------|--------------|----------|
| **Pak inject** (`inject_voices.py`, `install_patch.py --voices`) | `Resource/Voices/...` (replaces Russian clips in-place) | `original` | ScummVM loose/pak, retail `shveik.exe` |
| **Translated folder** (loose or custom engine) | `Resource/Voices_en/...` | `translated` | Custom engine / ScummVM build with `qd_localization` |

Most community patches use **pak inject** or loose copies into `Resource/Voices/` so players keep `voice_mode=original`.

### Reference: map lines to audio files

```bash
python3 tools/fix_voice_paths.py    # refresh voice_file / sound_ref in CSV
python3 tools/verify_voices.py      # must pass before recording dubs
```

`voice_file` uses Windows-style paths, e.g. `Resource\Voices\Комната Швейка\ep01_033.ogg`. Multiple files are pipe-separated when one text id reuses several clips.

### Extract reference clips (for actors / TTS)

```bash
python3 tools/extract_voices.py
# → translation/voice_samples/<character>/*.ogg
```

### Record a voice pack

1. Use the `voice_file` column — **filenames and folders must match exactly** (3,946 voiced lines).
2. Place `.ogg` files under `patch/voices_en/` (or `patch/voices_de/`, etc.) mirroring pak layout:

   ```
   patch/voices_en/
     Комната Швейка/
       ep01_033.ogg
     Кухня Швейка/
       ep02_152.ogg
   ```

   You may also use full paths: `patch/voices_en/Resource/Voices/Комната Швейка/ep01_033.ogg`

3. Install:

   **Pak-based (replaces Russian voices in `Resource/Voices/`):**
   ```bash
   python3 tools/inject_voices.py --game-dir /path/to/game --voices-dir patch/voices_en
   # or full patch:
   python3 tools/install_patch.py --game-dir /path/to/game --voices patch/voices_en
   ```

   **ScummVM loose files (same in-place layout):**
   ```bash
   # Mirror voice_file paths under game/Resource/Voices/
   cp -r patch/voices_en/* /path/to/game/Resource/Voices/
   ./deploy /path/to/game   # if you also need text/UI
   ```

   **Alternate: `Voices_en/` folder (engine `voice_mode=translated` only):**
   ```bash
   # Copy to game/Resource/Voices_en/ with same subfolders
   # Set voice_mode=translated in qd_game.ini — requires qd_localization in runtime
   ```

4. Re-run `verify_voices.py` after CSV edits.

---

## UI graphics (menus, buttons, startup quote)

Menu labels are **baked into QDA/TGA images**, not the text database.

### Export → edit → import

```bash
# Export Russian UI sprites to PNG
python3 tools/qda_edit.py export

# Edit PNGs in patch/qda_work/  (GIMP/Krita — do NOT change canvas size)
# Multi-frame cursors: edit *_f00.png, *_f01.png, ...
# Startup epigraph PNG: patch/qda_work/startup/заставка стартовая надпись.png

# Pack back to QDA → patch/overrides/Resource/
python3 tools/qda_edit.py import

# Deploy
./deploy
```

Startup quote source QDA:

`Resource/Комната Швейка/Animation/заставка стартовая надпись.qda`

Import a single asset:

```bash
python3 tools/qda_edit.py import \
  --source "patch/ui_src/Resource/Комната Швейка/Animation/заставка стартовая надпись.qda"
```

### Transparency (critical)

QDA sprites with alpha must encode transparent pixels as **`0xFF000000`** in RLE data, not `0x00000000`. `tools/qda_tools.py` handles this on import. Black boxes behind UI sprites (e.g. volume ladybugs) mean you need to re-import with current tools:

```bash
python3 tools/qda_edit.py import && ./deploy
```

### Extract UI from pak (first-time setup)

```bash
python3 tools/extract_ui.py --all
# → patch/ui_src/Resource/...
```

### Letters, inventory items, and readable documents

Dialogue subtitles cover spoken lines only. **Letters, flyers, postcards, cipher sheets, and inventory examine screens** are baked into QDA art under `Resource/Инвентарь/` (238 files) — not in `schweik_dialogue.csv`.

```bash
# One-shot: pull sources, PNGs for GIMP, manifest for translators
python3 tools/extract_letters.py
# → patch/letters/png/Инвентарь/Описания/desc full_*.png  (readable close-ups)
# → translation/letters_manifest.csv
```

**Translate → import → deploy (same loose-folder rule as menus):**

```bash
# Edit PNGs under patch/qda_work/ (keep canvas size!)
# Pack English QDAs into overrides:
python3 tools/qda_edit.py import --work patch/qda_work --output patch/overrides/Resource

# MUST deploy full folder caches first, then your overrides:
python3 tools/verify_loose.py
./deploy
```

`./deploy` always installs the **full** `Resource/Инвентарь/` tree from `patch/resource_loose/` before overlaying any English files. Without this, a single translated letter QDA would shadow the pak and break every other inventory image.

**Two inventory folders (do not confuse them):**

| Folder | Files | Content |
|--------|-------|---------|
| `Resource/Inventory/` | 6 | Top inventory bar UI (scroll arrows, main-menu button) |
| `Resource/Инвентарь/` | 238 | Item icons, letter close-ups, `Описания/desc full_*` examine screens |

### Optional: read baked Russian text from UI crops

```bash
python3 tools/export_ui_text.py --vision   # requires local Ollama vision model
# → translation/ui_strings.csv
```

---

## In-game map (`Resource/Карта`)

Opened from the in-game menu (scene `1Карта`). **Not** the playing-card inventory items (`карта дама`, etc.).

### Asset breakdown (21 files)

| Kind | Files | Translate? |
|------|-------|------------|
| **Background** | `Static/fon.tga` (800×600 parchment Prague map) | Optional — retail title is German (*Stadtplan von Prag*); locations are colored blocks, not Russian labels |
| **Label sprites** | `трактир.qda`, `кухня швейка.qda` + `_подсветка` variants (209×62) | **Yes** — baked Russian typography |
| **Click zones** | 8 locations × normal + `_подсветка` (800×600, mostly transparent) | **No** — keep pixel geometry; these are hit-test/highlight masks |

**Locations (click zones):** train station, square, asylum, tavern, Schweik's kitchen, police station, park, Katz's house, Lukash's apartment, temple.

**Schweik's map dialogue** (when a zone is locked) is already in `translation/schweik_dialogue.csv` under `Прочие.Карта.*` — subtitles only, no extra UI work.

### Start over (bad label pass / keep custom `fon.png`)

```bash
# Re-pull retail QDAs from pak, wipe packed label overrides, keep your Static/fon.png
python3 tools/extract_map.py --reset-overrides --keep-work-static --export-all-animations

# Only deploy the new background until labels are re-edited:
# (pack fon.png -> patch/overrides/Resource/Карта/Static/fon.tga, then ./deploy)
```

Retail click-zone PNGs land in `patch/qda_work/Карта/Animation/zones/` (800×600 overlays). Edit hover variants (`*_подсветка.png`) here; `qda_edit.py import` picks them up from `zones/` automatically.

```bash
python3 tools/qda_edit.py import \
  --source patch/ui_src/Resource/Карта/Animation/площадь_подсветка.qda \
  --work patch/qda_work/Карта/Animation
./deploy
```

### Extract → edit → import

```bash
# One-shot: pull sources, PNGs for GIMP, and translation/map_strings.csv
python3 tools/extract_map.py

# Edit only the 4 label PNGs (and optionally Static/fon.png):
#   patch/qda_work/Карта/Animation/трактир.png
#   patch/qda_work/Карта/Animation/трактир_подсветка.png
#   patch/qda_work/Карта/Animation/кухня швейка.png
#   patch/qda_work/Карта/Animation/кухня швейка_подсветка.png
# Keep canvas size 209×62. Match the highlight style on *_подсветка variants.

# Pack label QDAs (and fon.tga if you edited it):
python3 tools/qda_edit.py import \
  --source patch/ui_src/Resource/Карта/Animation
# For fon.tga: copy edited TGA to patch/overrides/Resource/Карта/Static/fon.tga
# (use tools/tga_convert conventions — deploy runs ensure_engine_tga on .tga)

./deploy
```

Inventory reference: `translation/map_strings.csv` (generated by `extract_map.py`).

### ScummVM deploy note

If **any** file under `patch/overrides/Resource/Карта/` is overridden, `./deploy` copies the **full** `Resource/Карта/` tree from the loose cache (all 21 files) before applying your edits — same partial-folder rule as Animation/Inventory.

Suggested English labels:

| Russian (retail) | English |
|------------------|---------|
| `трактир "У чаши"` | `Tavern "At the Cup"` |
| `кухня Швейка` | `Schweik's Kitchen` |

---

## Deploy & install methods

### Loose deploy (`./deploy`)

| Flag | Effect |
|------|--------|
| *(none)* | Text + graphics + animation cache + ini + ScummVM label |
| `--text-only` | Dialogue only (no UI / animation cache) |
| `--graphics-only` | UI only (no btdb) |
| `--skip-ini` | Do not overwrite `qd_game.ini` |
| `--skip-scummvm` | Do not touch `scummvm.ini` |

```bash
./deploy
./deploy "/path/to/game/folder"
./deploy --text-only
./deploy "/path/to/game" --graphics-only --skip-scummvm
```

### Pak rewrite (retail Windows, slow ~1.2 GB)

```bash
./install
python3 tools/install_patch.py --game-dir "/path/to/game" --no-cd
python3 tools/install_patch.py --game-dir "/path/to/game" --voices patch/voices_en
python3 tools/install_patch.py --game-dir "/path/to/game" --restore   # undo pak patch
```

| `install_patch.py` flag | Effect |
|-------------------------|--------|
| `--text-only` | Dialogue only |
| `--graphics-only` | UI only |
| `--no-cd` | Merge `resource1.pak` into `resource0.pak` first |
| `--voices DIR` | Inject `.ogg` into `Resource/Voices/` in pak |
| `--restore` | Restore `resource0.pak` from backup |

### ScummVM rules (important)

**Golden rule:** if *any* file exists loose under `game/.../Resource/<folder>/`, ScummVM does **not** fall back to `resource0.pak` for other files in that same folder. Always deploy the **full** pak tree for the folder first, then overlay `patch/overrides/`.

- **Do not** copy a single edited QDA/TGA into the game folder by hand — use `./deploy`.
- **Do not** deploy a partial `Resource/Animation/` from UI overrides alone — missing walk-cycle QDAs make **characters vanish**.
- **Do not** deploy loose `Resource/Cursors/default.tga` only — use pak default + animation loose set from deploy.
- **Do** run `verify_loose.py` after adding image overrides to a new Resource folder.

`./deploy` builds and installs unified caches under `patch/resource_loose/Resource/<folder>/`:

| Folder | When | Why |
|--------|------|-----|
| `Animation/` | Always | 255 top-level QDAs referenced by `qd_game.qml` |
| `Sound/`, `Music/` | Always | Cyrillic paths fail in pak on ScummVM |
| `Инвентарь/` | Always | Letters, item icons, examine screens (readable image text) |
| `Interface/`, `Inventory/` | When overrides exist | Full menu / inventory-bar UI |
| `<room>/` (e.g. `Карта/`) | When overrides exist | Map labels, startup quote, death screen, etc. |

Rebuild caches manually (after game/pak update or cache corruption):

```bash
python3 tools/extract_animation_loose.py --force
python3 tools/verify_loose.py
python3 tools/verify_animations.py
./deploy
```

### ScummVM library label vs detection

| Setting | Value | Why |
|---------|-------|-----|
| `qd_game.ini` → `language` | `english` | In-game subtitle language |
| `scummvm.ini` → `language` | `ru` | Stock ScummVM only detects Russian retail data |
| `scummvm.ini` target | `shveik-ru` | Setting `language=en` causes “Couldn't identify game” |
| Library description | Windows/English | Cosmetic; set by `configure_scummvm.py` via `./deploy` |

Optional native English detection: build ScummVM with `scummvm/shveik_english_detection.patch` (uses `scummvm_english.marker` from `./deploy`).

---

## Verification checklist

Before sharing a patch build:

```bash
python3 tools/verify_voices.py
python3 tools/verify_loose.py
python3 tools/verify_animations.py
python3 tools/import_text.py
./deploy
```

Playtest in ScummVM:

- [ ] Translated subtitles in first dialogue scene
- [ ] Characters visible (walk cycles load)
- [ ] Mouse cursor visible
- [ ] Main menu / volume ladybugs have transparent backgrounds
- [ ] Startup epigraph shows your translation (if edited)
- [ ] Voices play as expected (`original` = Russian, or your injected dubs)

---

## Tool reference

| Tool | Purpose |
|------|---------|
| `deploy` / `deploy_loose.py` | One-command loose-file install |
| `configure_scummvm.py` | Relabel ScummVM entry (description only; keeps `shveik-ru`) |
| `extract_animation_loose.py` | Build unified ScummVM loose caches (`patch/resource_loose/`) |
| `verify_loose.py` | Verify every required Resource folder cache is complete vs pak |
| `verify_animations.py` | Verify Animation cache covers all QML top-level Animation refs |
| `extract_letters.py` | Extract letters/documents from `Resource/Инвентарь/` for translation |
| `fix_qml_states.py` | Normalize `отработано` → `отработан` in `qd_game.qml` (ScummVM) |
| `extract_map.py` | Extract in-game map assets + `translation/map_strings.csv` |
| `export_text.py` | Game → `schweik_dialogue.csv` |
| `import_text.py` | CSV → `patch/shveik_en.btdb` (hard-coded `english` column today) |
| `fix_voice_paths.py` | Refresh `voice_file` / `sound_ref` columns |
| `verify_voices.py` | Validate CSV voice paths vs `qd_game.qml` |
| `translate_ollama.py` | Batch-translate empty CSV cells |
| `extract_voices.py` | Pull reference `.ogg` samples per character |
| `inject_voices.py` | Inject voice pack into `resource0.pak` at `Resource/Voices/` |
| `qda_edit.py` | Export/import UI sprites (QDA ↔ PNG) |
| `qda_tools.py` | Low-level QDA RLE codec (used by qda_edit) |
| `extract_ui.py` | Pull UI assets from pak → `patch/ui_src` |
| `export_ui_text.py` | OCR-style UI string export |
| `restore_cursors.py` | Reset cursor QDAs from pristine `ui_src` |
| `install_patch.py` | Full pak-based patch (text, UI, voices) |
| `inject_ui.py` | Inject UI files into pak only |
| `extract_schweik.py` | Install game from CD images |
| `nocd_patch.py` | Merge `resource1.pak` into `resource0.pak` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Russian subtitles after deploy | `python3 tools/import_text.py && ./deploy`; confirm `language=english` in game `qd_game.ini` |
| ScummVM “Couldn't identify game” | Run `./deploy`; ensure `scummvm.ini` has `language=ru` and target `shveik-ru` |
| Characters invisible | Run `./deploy` (installs animation loose set) |
| Cursor missing | Same — need cursor QDAs in loose Animation set |
| Black boxes on UI / volume bugs | Re-run `python3 tools/qda_edit.py import` with current `qda_tools.py`, then `./deploy` |
| Garbled text / crash | Never hand-edit `.btdb`; rebuild with `import_text.py` |
| Blank PNGs in GIMP | Re-export: `python3 tools/qda_edit.py export` |
| Wrong voice mapping | `fix_voice_paths.py` then `verify_voices.py` |
| ScummVM spam: `Unknown state 'отработан'` | Run `./deploy` (installs `patch/qd_game.qml`); or `python3 tools/fix_qml_states.py` |
| English voices silent | Confirm files match `voice_file` paths; for pak inject use `Resource/Voices/`, not `Voices_en/`, with `voice_mode=original` |
| `NOT FOUND` / `audioStream is null` for `Resource/Sound/Кладбище/...` | Run `./deploy` — installs full `Resource/Sound/` and `Resource/Music/` loose caches (Cyrillic pak paths fail in ScummVM) |
| Inventory letters / examine screens missing or broken | Run `./deploy` — installs full `Resource/Инвентарь/` (~238 files); verify with `verify_loose.py` |
| Translated letter QDA breaks other inventory images | Partial loose folder — run `./deploy` (full cache first, overrides second); never copy single QDAs by hand |

More install detail: [INSTALL.md](../INSTALL.md). Engine build notes: [ENGINE.md](ENGINE.md).

---

## Contributing back

1. Fork the repo and work on a branch (`localization/<lang>`).
2. Keep game assets out of git.
3. Dialogue: PR updates to `translation/schweik_dialogue.csv` only (not regenerated btdb unless release tagging).
4. UI: PR PNGs or QDAs under `patch/overrides/` plus `qda_work` sources if useful.
5. Note ScummVM vs retail testing in PR description.
6. Update **this file** if you add tools, columns, deploy steps, or engine hooks.

---

## Maintainer changelog (this document)

| Date | Change |
|------|--------|
| 2026-07-07 | Initial guide: English CSV workflow, voices, UI QDA, ScummVM animation cache, `language=ru` requirement |
| 2026-07-07 | Expanded: TOC, fork playbook, language fork checklist, deploy/install flags (`--skip-ini`), voice install paths (`Voices/` vs `Voices_en/`), ScummVM detection patch note |
| 2026-07-07 | Animation fix: deploy all 255 top-level Animation QDAs + Inventory/room Animation caches; added `verify_animations.py` |
| 2026-07-07 | QML fix: `fix_qml_states.py` + `patch/qd_game.qml` for ScummVM `отработан` state warnings |
| 2026-07-07 | Map guide: `extract_map.py`, `translation/map_strings.csv`; room loose cache now copies full `Resource/<room>/` |
| 2026-07-07 | Sound/Music loose caches: full `Resource/Sound/*` + `Resource/Music/*` on every `./deploy` |
| 2026-07-07 | Unified `resource_loose/` cache; always deploy `Resource/Инвентарь/`; added `verify_loose.py` and letters workflow |