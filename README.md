# The Adventures of the Good Soldier Schweik — English Patch

Community English localization for *Похождения бравого солдата Швейка* (1C / KD Vision, 2007), built on the open-source **qdEngine**.

**Version 0.9.0** (2026-11-10). English dialogue on the original Russian voices. You play it in ScummVM. Nothing here needs to be compiled.

Play the full game in **English** with the original Russian voice acting, via **ScummVM** or the retail Windows executable. No compiler required for players — only Python and a legal copy of the game. This repository does not contain the game.

![qdEngine logo](qd_splash.png)

## Features

- **4,434 lines of dialogue** exported, translated, and packable as `shveik_en.btdb`
- **English subtitles + original Russian voices** (recommended default)
- **Voice file mapping** — every voiced line in `translation/schweik_dialogue.csv` links to its `.ogg` path for dubbing or TTS
- **Loose-file deployment** — `./deploy` drops patched files next to the game; ScummVM reads them before `resource0.pak` (fast, reversible, no 1.2 GB pak rewrite)
- **Image tools** — export, review, and pack signs, letters, and menu art. That art is not finished, and it is not in this release
- **Translation toolchain** — export/import CSV, Ollama batch translate, GIMP round-trip for UI sprites, voice inject, verification scripts
- **qdEngine source** — original C++ engine (GPLv3) with localization hooks

## What you need

| Requirement | Notes |
|-------------|--------|
| **Legal game copy** | Original CDs or your own disc images. This repo does **not** ship game assets. |
| **Python 3.10+** | For patch tools only |
| **ScummVM** (recommended) | With qdEngine / `shveik` target support |
| **Pillow** | `pip install pillow` — for UI sprite tools |

## Quick install (players)

### 1. Install the game

Install from CD, or extract with:

```bash
python3 tools/extract_schweik.py
```

Your game folder should contain `qd_game.qml`, `qd_game.ini`, and `Resource/resource0.pak`.

### 2. Clone this repository

```bash
git clone https://github.com/YOUR_USER/qdEngine.git
cd qdEngine
```

### 3. Point the patch at your game

Either copy/link the game into the repo:

```
qdEngine/game/shveik/app/   ← qd_game.qml, Resource/, etc.
```

Or pass your install path to `./deploy` (step 4).

### 4. Deploy the English patch

```bash
pip install pillow
./deploy
# or: ./deploy "/path/to/your/Schweik/folder"
```

This copies:

- `patch/shveik_en.btdb` → `Resource/shveik_en.btdb` and `Resource/shveik.btdb`
- `patch/overrides/Resource/...` → loose UI graphics (menus, cursors, etc.)

Set `language=english` in `qd_game.ini` (included in a typical install). Restart ScummVM completely after deploying.

### 5. Play

Add the game folder in ScummVM and launch. Dialogue appears in English. The voices stay the original Russian performances. See [Why there is no English dub](#why-there-is-no-english-dub).

`./deploy` sets `language=english` in `qd_game.ini` (in-game text) and relabels the ScummVM library **description** as Windows/English. The ScummVM config keeps `language=ru` / target `shveik-ru` — stock ScummVM only detects the Russian retail data and will not launch if you set `language=en` there.

## Install options

| Method | Command | Best for |
|--------|---------|----------|
| **Loose files** (recommended) | `./deploy` | ScummVM, fast iteration, easy undo |
| **Subtitles only** | `./deploy --text-only` | Dialogue test without UI overrides |
| **Graphics only** | `./deploy --graphics-only` | UI test without touching text DB |
| **Pak rewrite** (slow) | `./install` | Legacy Windows install that patches `resource0.pak` inside the archive |

See [INSTALL.md](INSTALL.md) for Windows executable installs, voice packs, and restore instructions.

## What is translated

| Content | Count | Format | Tooling |
|---------|-------|--------|---------|
| Dialogue & subtitles | 4,434 lines | `translation/schweik_dialogue.csv` → `patch/shveik_en.btdb` | `export_text.py`, `import_text.py`, `translate_ollama.py` |
| Voiced lines | 3,946 | CSV `voice_file` column → `Resource/Voices/.../*.ogg` | `fix_voice_paths.py`, `verify_voices.py` |
| Subtitle-only lines | 488 | CSV only (examine text, topic labels — no voice in original) | — |
| Menu & dialog UI | 50 QDA + 15 TGA | GIMP → `qda_edit.py` | `extract_ui.py`, `qda_edit.py` |
| Startup quote (Hasek epigraph) | 1 QDA | `patch/qda_work/startup/` | manual export/import |
| English voice pack (optional) | 3,946+ OGG | `patch/voices_en/` mirroring `Resource/Voices/` | `inject_voices.py` |

UI button labels are **baked into images**, not the text database. Dialogue is in the CSV.

## Why there is no English dub

This release is English dialogue on the original Russian voice acting. I left the performances alone on purpose.

The comedy is in the delivery: the timing, the muttering, the way Schweik sounds pleased with himself. Replacing that with a generated English voice would read the subtitles back in one tone. There are 3,946 voiced lines, and Schweik alone is 2,326 of them. Names such as Švejk, Palivec, and Katz come out wrong unless someone fixes the pronunciation line by line.

The mapping is ready if you want to record it or commission it. Every voiced row in `translation/schweik_dialogue.csv` has a `voice_file` path. Match those filenames under `patch/voices_en/`, then install with `tools/inject_voices.py`. Reference clips per character come from `python3 tools/extract_voices.py`. The steps are in [docs/LOCALIZATION.md](docs/LOCALIZATION.md#voices).

## What's in 0.9.0

- All 4,434 dialogue lines are translated in `translation/schweik_dialogue.csv` and built into `patch/shveik_en.btdb`.
- `./deploy` copies that text into a legal install and sets `language=english`. Voices stay Russian (`voice_mode=original`).
- All 3,946 spoken lines are mapped to their original `.ogg` files, so someone else can dub them.
- ScummVM install notes, including why the library entry stays `shveik-ru`.
- Tools for the picture pass, and localization hooks in the qdEngine source (GPLv3, forked from [KD-lab-Open-Source/qdEngine](https://github.com/KD-lab-Open-Source/qdEngine)).

Not in this version: signs, letters, the newspaper, inventory screens, the Bible, credits, and the cipher page. Those words are painted into pictures. The cipher page has to keep lining up with the punched card, so it cannot be reflowed like a subtitle. English voices are not included. The retail game, disc images, and extracted voice clips are not in the repository.

## Roadmap

1. **1.0** — finish the readable pictures, play the game through in ScummVM, and ship that art with the patch.
2. **English dub** — open for a contributor. The file map and install tool are already here.
3. **Other languages** — reuse the CSV and `./deploy` path. See [docs/LOCALIZATION.md](docs/LOCALIZATION.md).

## Repository layout

```
qdEngine/
├── README.md                 ← you are here
├── INSTALL.md                ← detailed install & troubleshooting
├── docs/LOCALIZATION.md      ← add languages, voices, UI; contributor guide
├── deploy                    ← one-command loose-file install (ScummVM)
├── install                   ← full pak rewrite (slow)
├── translation/
│   ├── schweik_dialogue.csv  ← master dialogue translation (4,434 rows)
│   └── ui_strings.csv        ← UI label helper (optional)
├── patch/
│   ├── shveik_en.btdb        ← built English text database
│   ├── overrides/Resource/   ← loose UI files (QDA, TGA)
│   └── ui_src/               ← extracted Russian UI sources
├── tools/                    ← Python patch & translation utilities
├── game/shveik/app/          ← your game install (not in git — see .gitignore)
└── src/QD/                   ← qdEngine C++ source (GPLv3)
```

## For contributors

**Full guide:** [docs/LOCALIZATION.md](docs/LOCALIZATION.md) — adding languages, voices, UI graphics, deploy, ScummVM quirks, and tool reference.

### Dialogue translators

```bash
python3 tools/export_text.py --game-dir /path/to/game
# Edit translation/schweik_dialogue.csv (english column)
python3 tools/import_text.py
python3 tools/fix_voice_paths.py   # refresh voice_file columns
python3 tools/verify_voices.py
./deploy
```

### UI artists (menus, startup screen)

```bash
python3 tools/qda_edit.py export
# Edit PNGs in patch/qda_work/ (GIMP/Krita — keep canvas size!)
python3 tools/qda_edit.py import
./deploy
```

Startup epigraph: `Resource/Комната Швейка/Animation/заставка стартовая надпись.qda`

### Voice actors / TTS

1. Use the `voice_file` column in `schweik_dialogue.csv` — filenames must match exactly.
2. Place recordings under `patch/voices_en/` with the same folder structure as `Resource/Voices/`.
3. Install:

```bash
python3 tools/inject_voices.py --game-dir /path/to/game --voices-dir patch/voices_en
# or use install_patch.py --voices for pak-based installs
```

Extract reference clips per character:

```bash
python3 tools/extract_voices.py
```

### Tool reference

| Tool | Purpose |
|------|---------|
| `deploy` / `deploy_loose.py` | Copy patch files into game folder |
| `install_patch.py` | Patch inside `resource0.pak` (Windows retail) |
| `export_text.py` | Game → `schweik_dialogue.csv` |
| `import_text.py` | CSV → `patch/shveik_en.btdb` |
| `fix_voice_paths.py` | Refresh `voice_file` / `sound_ref` in CSV |
| `verify_voices.py` | Check CSV voice paths against `qd_game.qml` |
| `translate_ollama.py` | Batch translate via local Ollama |
| `qda_edit.py` | Export/import UI sprites (QDA ↔ PNG) |
| `extract_ui.py` | Pull UI assets from `resource0.pak` |
| `restore_cursors.py` | Reset cursor QDAs from pristine sources |

## Undo / restore

Delete loose patch files under your game's `Resource/` folder (e.g. `shveik.btdb`, `shveik_en.btdb`, overridden QDAs). ScummVM falls back to the original `resource0.pak`.

For pak-based installs:

```bash
python3 tools/install_patch.py --game-dir /path/to/game --restore
```

## qdEngine (source code)

This repository also contains the **qdEngine** game engine (C++, GPLv3), originally by KD Vision. Engine code lives under `src/QD/` and `src/XLibs/`.

Building from source requires **Visual Studio 2003** on Windows and is only needed if you are hacking the engine itself — not for playing the English patch.

See [docs/ENGINE.md](docs/ENGINE.md) for engine build notes.

Community chat (engine): https://t.me/kdlab_association_chat

## License

- Engine code (except third-party libraries): **GPLv3** — see [LICENSE](LICENSE)
- Third-party libraries: their respective licenses as noted in source
- **Game assets** (voices, graphics, scripts inside `resource0.pak`) are **not** included and remain property of the original rights holders. You must own a legal copy of the game.

## Disclaimer

This project is a fan/community localization. It is not affiliated with 1C, KD Vision, or the Hašek estate. Do not redistribute copyrighted game files — only patch tools, translations, and instructions.