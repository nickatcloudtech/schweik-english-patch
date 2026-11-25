# Installation Guide

Play *The Adventures of the Good Soldier Schweik* in English without compiling the engine.

## What you need

1. A **legal copy** of the game (CDs or disc images)
2. **Python 3.10+**
3. **Pillow** — `pip install pillow` (for UI tools only)
4. This repository

## Recommended: ScummVM + loose files (`./deploy`)

ScummVM reads loose files in the game folder **before** `resource0.pak`. The patch copies English assets alongside the original game — fast, safe, and easy to undo.

### Step 1 — Install the game

Install from CD, or:

```bash
python3 tools/extract_schweik.py
```

Expected layout:

```
YourGameFolder/
  qd_game.qml
  qd_game.ini
  Resource/
    resource0.pak
```

### Step 2 — Deploy the patch

From the repository root:

```bash
pip install pillow
./deploy
```

Or point at your install:

```bash
./deploy "/path/to/YourGameFolder"
```

Default target if omitted: `game/shveik/app/` inside the repo.

### What `./deploy` installs

| Source | Destination | Purpose |
|--------|-------------|---------|
| `patch/shveik_en.btdb` | `Resource/shveik_en.btdb` | English text (used when `language=english`) |
| `patch/shveik_en.btdb` | `Resource/shveik.btdb` | Fallback text database |
| `patch/overrides/Resource/**` | `Resource/**` | English UI graphics (menus, cursors, etc.) |

If `patch/shveik_en.btdb` is older than `translation/schweik_dialogue.csv`, deploy rebuilds it automatically.

### Step 3 — Configure language

In `qd_game.ini`:

```ini
[localization]
language=english
voice_mode=original
```

- `language=english` — load English text from `shveik_en.btdb`
- `voice_mode=original` — keep Russian voice acting (subtitle mode)

### Step 4 — Play in ScummVM

Add the game folder, launch, and **restart ScummVM** after each `./deploy` so new loose files are picked up.

`./deploy` also:
- writes `scummvm_english.marker` so patched installs can be identified
- relabels your `scummvm.ini` **description** as Windows/English (keeps `language=ru` and target `shveik-ru` so stock ScummVM can still identify the game)

For a native `shveik-en` target on add, apply `scummvm/shveik_english_detection.patch` and rebuild ScummVM. Until then: add the game, run `./deploy`, and the library shows English while keeping the working `shveik-ru` id.

### Deploy options

```bash
./deploy --text-only      # dialogue only, skip UI graphics
./deploy --graphics-only  # UI only, skip text database
```

---

## Alternative: Windows retail executable (pak patch)

Patches dialogue (and optional voices) **inside** `resource0.pak`. Slower (~1.2 GB rewrite) but works with `shveik.exe` directly.

### English subtitles + Russian voices

```bash
python3 tools/install_patch.py --game-dir "C:/Path/To/Schweik" --no-cd
```

### English subtitles + English voice pack

Not part of this release. The shipped patch keeps the Russian performances, and the dub is open for someone else to record. Reasons and the file map are in the README section "Why there is no English dub".

```bash
python3 tools/install_patch.py --game-dir "C:/Path/To/Schweik" --no-cd --voices patch/voices_en
```

### Restore original pak

```bash
python3 tools/install_patch.py --game-dir "C:/Path/To/Schweik" --restore
```

Restores `resource0.pak` from `resource0.pak.original`.

---

## Voice pack layout

Each CSV row has a `voice_file` column, e.g.:

```
Resource\Voices\Комната Швейка\ep01_033.ogg
```

English recordings must use the **same filename** and folder structure:

```
patch/voices_en/
  Комната Швейка/
    ep01_033.ogg
  Кухня Швейка/
    ep02_152.ogg
```

Inject loose voices (ScummVM) or into pak:

```bash
python3 tools/inject_voices.py --game-dir /path/to/game --voices-dir patch/voices_en
```

---

## For translators

```bash
# Export from game
python3 tools/export_text.py --game-dir /path/to/game

# Edit translation/schweik_dialogue.csv

# Build text database
python3 tools/import_text.py

# Verify voice paths
python3 tools/fix_voice_paths.py
python3 tools/verify_voices.py

# Install
./deploy
```

### UI graphics (menus, startup quote)

```bash
python3 tools/qda_edit.py export
# Edit PNGs in patch/qda_work/ — do not change canvas dimensions
python3 tools/qda_edit.py import
./deploy
```

---

## Undo loose-file patch (ScummVM)

Delete these from your game folder:

- `Resource/shveik.btdb`
- `Resource/shveik_en.btdb`
- Any files you added under `Resource/` from `patch/overrides/`

The game falls back to the original pak contents.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Still Russian subtitles | Run `python3 tools/import_text.py` then `./deploy`. Confirm `language=english` in `qd_game.ini`. Restart ScummVM. |
| Garbled / crash on text | Rebuild btdb with our tools (CP1251 encoding). Do not hand-edit the binary. |
| UI buttons blank in GIMP | Re-export with `python3 tools/qda_edit.py export` (alpha fix is in `qda_tools.py`). |
| Characters invisible / cursor missing | Run `./deploy` — it installs all 255 top-level `Resource/Animation/` QDAs. ScummVM does not fall back to the pak for missing files in a loose Animation folder. Verify with `python3 tools/verify_animations.py`. |
| Cursor has solid background | `python3 tools/restore_cursors.py` then inject into pak: `python3 tools/install_patch.py --graphics-only` (not `./deploy`) |
| `deploy --text-only` ignored | Use `./deploy --text-only` (flags must come after `./deploy`) |
| Game folder not found | Pass full path: `./deploy "/path/to/folder/with/qd_game.qml"` |
| Want Russian back (pak install) | `install_patch.py --restore` |

---

## What is not included

This repository ships **tools and translations only**. You must provide your own copy of the game. Game assets (graphics, audio, scripts) remain copyrighted by their original owners.