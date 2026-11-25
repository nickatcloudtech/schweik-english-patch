# ScummVM patches for the English Schweik patch

Stock ScummVM 2.x can run the game with `./deploy`, but two qdengine fixes are
recommended for correct main-menu rendering and nested UI overrides.

## Patches (apply in order)

1. **`qdengine_nested_loose_files.patch`** — optional; only needed if you keep
   nested Interface QDAs as loose files on disk. `./deploy` now puts button
   QDAs in `resource0.pak` only, so this patch is optional for menu buttons.

2. **`qdengine_main_menu_redraw.patch`** — **required for main menu buttons and
   background.** Without it, only the volume sliders repaint each frame; the
   title art and Load/Save/Exit buttons stay black.

## Build ScummVM with patches

```bash
git clone https://github.com/scummvm/scummvm.git
cd scummvm
patch -p1 < /path/to/qdEngine/scummvm/qdengine_main_menu_redraw.patch
# optional:
# patch -p1 < /path/to/qdEngine/scummvm/qdengine_nested_loose_files.patch
./configure
make -j$(nproc)
```

Run your patched `scummvm` binary instead of the distro/snap build after
`./deploy`.

## Verify assets (no ScummVM build needed)

```bash
./deploy
python3 tools/verify_menu_deploy.py
python3 tools/render_main_menu.py   # writes patch/main_menu_composite.png
```

If the composite PNG looks correct but the game still shows only volume
sliders, you need the main-menu redraw patch.