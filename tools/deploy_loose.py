#!/usr/bin/env python3
"""
Copy English patch files as LOOSE files next to the game.

ScummVM checks loose files before resource0.pak, but only for paths up to four
directory levels below the game folder (SearchMan depth limit). Shallow UI such
as ``Resource/Interface/Main menu/fon.tga`` and ``music.qda`` load loose; nested
button QDAs under ``exit/``, ``load/``, etc. do not — those overrides are also
injected into resource0.pak by this script.

Golden rule: if ANY file exists loose under Resource/<folder>/, ScummVM will
NOT fall back to the pak for other files in that folder. ./deploy always copies
the FULL pak tree for affected folders first, then overlays patch/overrides/.

Layout:
  patch/resource_loose/Resource/<folder>/  — full retail trees (generated)
  patch/overrides/Resource/...             -> game/.../Resource/...
  patch/shveik_en.btdb                     -> game/.../Resource/shveik.btdb
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.configure_scummvm import configure_scummvm
from tools.pak_paths import decode_pak_path
from tools.pak_utils import inject_files
from tools.scummvm_loose import interface_override_relatives, scummvm_loose_visible
from tools.extract_animation_loose import (
    ALWAYS_LOOSE_FOLDERS,
    CONDITIONAL_LOOSE_FOLDERS,
    DEFAULT_RESOURCE_LOOSE_ROOT,
    INVENTORY_ITEMS_FOLDER,
    build_loose_caches,
    discover_override_resource_folders,
    folder_cache_is_stale,
    animation_cache_is_stale,
)
from tools.import_text import import_dialogue
from tools.tga_convert import ensure_engine_tga

DEFAULT_GAME = ROOT / "game" / "shveik" / "app"
DEFAULT_OVERRIDES = ROOT / "patch" / "overrides"
DEFAULT_CSV = ROOT / "translation" / "schweik_dialogue.csv"
DEFAULT_BTDB = ROOT / "patch" / "shveik_en.btdb"
DEFAULT_INI = ROOT / "patch" / "qd_game.ini"
DEFAULT_MARKER = ROOT / "patch" / "scummvm_english.marker"
DEFAULT_README = ROOT / "patch" / "readme_en.txt"
DEFAULT_QML_PATCH = ROOT / "patch" / "qd_game.qml"

# Never deploy partial top-level Resource folders from UI overrides alone.
# Full caches are deployed first; these folders are overlay-only from overrides.
LOOSE_SKIP_TOP_LEVEL = frozenset({"Animation", "Cursors"})


def _relative_resource_path(path: Path, resource_root: Path) -> Path:
    return path.relative_to(resource_root)


def should_skip_loose_deploy(relative: Path) -> bool:
    return bool(relative.parts) and relative.parts[0] in LOOSE_SKIP_TOP_LEVEL


def _prepare_deploy_bytes(path: Path, data: bytes) -> bytes:
    if path.suffix.lower() == ".tga":
        return ensure_engine_tga(data, path)
    return data


def _copy_cache_tree(
    cache_dir: Path,
    target_dir: Path,
    *,
    skip_relatives: set[Path] | None = None,
) -> list[Path]:
    if not cache_dir.exists():
        return []

    deployed: list[Path] = []
    for source in sorted(cache_dir.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(cache_dir)
        if skip_relatives and relative in skip_relatives:
            continue
        target = target_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        deployed.append(target)
    return deployed


def _any_cache_stale(
    pak_path: Path,
    resource_root: Path,
    overrides_dir: Path,
) -> bool:
    if animation_cache_is_stale(resource_root / "Animation"):
        return True
    for folder in ALWAYS_LOOSE_FOLDERS:
        if folder == "Animation":
            continue
        if folder_cache_is_stale(resource_root / folder, folder, pak_path):
            return True
    for folder in CONDITIONAL_LOOSE_FOLDERS:
        if (overrides_dir / "Resource" / folder).exists():
            if folder_cache_is_stale(resource_root / folder, folder, pak_path):
                return True
    for folder in discover_override_resource_folders(overrides_dir):
        cache_dir = resource_root / folder
        if folder_cache_is_stale(cache_dir, folder, pak_path):
            return True
    return False


def ensure_loose_caches(
    game_dir: Path,
    overrides_dir: Path,
    *,
    resource_root: Path = DEFAULT_RESOURCE_LOOSE_ROOT,
    pak_path: Path | None = None,
) -> None:
    pak = pak_path or (game_dir / "Resource" / "resource0.pak")
    if _any_cache_stale(pak, resource_root, overrides_dir):
        print(f"  building loose caches from {pak.name}")
        build_loose_caches(
            pak.resolve(),
            resource_root=resource_root.resolve(),
            overrides_dir=overrides_dir.resolve(),
        )


def deploy_resource_loose_caches(
    game_dir: Path,
    *,
    resource_root: Path = DEFAULT_RESOURCE_LOOSE_ROOT,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> dict[str, list[Path]]:
    """Deploy full Resource folder caches before patch overrides."""
    ensure_loose_caches(
        game_dir,
        overrides_dir,
        resource_root=resource_root,
        pak_path=pak_path,
    )

    deployed: dict[str, list[Path]] = {}
    resource_target = game_dir / "Resource"
    interface_skip = interface_override_relatives(overrides_dir)

    for folder in sorted(ALWAYS_LOOSE_FOLDERS):
        targets = _copy_cache_tree(resource_root / folder, resource_target / folder)
        if targets:
            deployed[folder] = targets

    for folder in sorted(CONDITIONAL_LOOSE_FOLDERS):
        if not (overrides_dir / "Resource" / folder).exists():
            continue
        skip = interface_skip if folder == "Interface" else None
        targets = _copy_cache_tree(
            resource_root / folder,
            resource_target / folder,
            skip_relatives=skip,
        )
        if targets:
            deployed[folder] = targets

    for folder in discover_override_resource_folders(overrides_dir):
        targets = _copy_cache_tree(resource_root / folder, resource_target / folder)
        if targets:
            deployed[folder] = targets

    return deployed


# Backward-compatible wrappers for verify_animations.py and older scripts.
def deploy_animation_loose(
    game_dir: Path,
    cache_dir: Path,
    *,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> list[Path]:
    ensure_loose_caches(game_dir, overrides_dir, pak_path=pak_path)
    return _copy_cache_tree(cache_dir, game_dir / "Resource" / "Animation")


def deploy_inventory_loose(
    game_dir: Path,
    cache_dir: Path,
    *,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> list[Path]:
    if not (overrides_dir / "Resource" / "Inventory").exists():
        return []
    ensure_loose_caches(game_dir, overrides_dir, pak_path=pak_path)
    return _copy_cache_tree(cache_dir, game_dir / "Resource" / "Inventory")


def deploy_sound_loose(
    game_dir: Path,
    cache_dir: Path,
    *,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> list[Path]:
    ensure_loose_caches(game_dir, overrides_dir, pak_path=pak_path)
    return _copy_cache_tree(cache_dir, game_dir / "Resource" / "Sound")


def deploy_music_loose(
    game_dir: Path,
    cache_dir: Path,
    *,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> list[Path]:
    ensure_loose_caches(game_dir, overrides_dir, pak_path=pak_path)
    return _copy_cache_tree(cache_dir, game_dir / "Resource" / "Music")


def deploy_interface_loose(
    game_dir: Path,
    cache_dir: Path,
    *,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> list[Path]:
    if not (overrides_dir / "Resource" / "Interface").exists():
        return []
    ensure_loose_caches(game_dir, overrides_dir, pak_path=pak_path)
    return _copy_cache_tree(cache_dir, game_dir / "Resource" / "Interface")


def deploy_room_animation_loose(
    game_dir: Path,
    cache_root: Path,
    *,
    overrides_dir: Path = DEFAULT_OVERRIDES,
    pak_path: Path | None = None,
) -> list[Path]:
    ensure_loose_caches(game_dir, overrides_dir, pak_path=pak_path)
    deployed: list[Path] = []
    for room in discover_override_resource_folders(overrides_dir):
        deployed.extend(_copy_cache_tree(cache_root / room, game_dir / "Resource" / room))
    return deployed


def _interface_loose_visible(relative: Path) -> bool:
    """True if ScummVM SearchMan can load this Interface path loose."""
    return scummvm_loose_visible(Path("Resource") / relative)


def _prune_nested_interface_loose(game_dir: Path) -> list[Path]:
    """Remove nested Interface files that ScummVM cannot see (pak-only paths)."""
    interface_dir = game_dir / "Resource" / "Interface"
    if not interface_dir.is_dir():
        return []

    removed: list[Path] = []
    for path in sorted(interface_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(game_dir / "Resource")
        if not _interface_loose_visible(relative):
            path.unlink()
            removed.append(path)
    return removed


def deploy_tree(source: Path, game_dir: Path) -> list[Path]:
    if not source.exists():
        return []

    deployed: list[Path] = []
    resource_root = source / "Resource"
    if not resource_root.exists():
        resource_root = source

    for path in resource_root.rglob("*"):
        if not path.is_file() or path.name == "manifest.csv":
            continue

        relative = _relative_resource_path(path, resource_root)
        if should_skip_loose_deploy(relative):
            continue
        if relative.parts and relative.parts[0] == "Interface" and not _interface_loose_visible(relative):
            continue

        target = game_dir / "Resource" / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        target.write_bytes(_prepare_deploy_bytes(path, path.read_bytes()))
        deployed.append(target)

    return deployed


def deploy_text(game_dir: Path, csv_path: Path, btdb_path: Path) -> list[Path]:
    """Deploy English subtitles.

    ScummVM/qdEngine with ``language=english`` in qd_game.ini loads
    ``Resource/shveik_en.btdb`` (see qdLocalization::resolve_text_database).
    We write both names so loose-file overrides work regardless of ini.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing translation CSV: {csv_path}")

    if not btdb_path.exists() or csv_path.stat().st_mtime > btdb_path.stat().st_mtime:
        print(f"  rebuilding {btdb_path.name} from {csv_path.name}")
        import_dialogue(csv_path, game_dir, btdb_path)

    resource_dir = game_dir / "Resource"
    resource_dir.mkdir(parents=True, exist_ok=True)

    deployed: list[Path] = []
    for name in ("shveik_en.btdb", "shveik.btdb"):
        target = resource_dir / name
        shutil.copy2(btdb_path, target)
        deployed.append(target)
    return deployed


def deploy_qml_patch(game_dir: Path, qml_patch: Path, source_qml: Path) -> Path | None:
    """Deploy patched qd_game.qml (state-name fixes for ScummVM)."""
    if not source_qml.exists():
        return None

    from tools.fix_qml_states import fix_qml_file

    if not qml_patch.exists() or source_qml.stat().st_mtime > qml_patch.stat().st_mtime:
        print(f"  building {qml_patch.name} from game script")
        fix_qml_file(source_qml, qml_patch)

    target = game_dir / "qd_game.qml"
    shutil.copy2(qml_patch, target)
    return target


def deploy_ini(game_dir: Path, ini_path: Path) -> Path | None:
    if not ini_path.exists():
        return None
    target = game_dir / "qd_game.ini"
    shutil.copy2(ini_path, target)
    return target


def _interface_override_sources(overrides_dir: Path) -> dict[str, tuple[Path, bytes]]:
    """Map pak archive paths to on-disk override sources and deploy-ready bytes."""
    prepared: dict[str, tuple[Path, bytes]] = {}
    resource_root = overrides_dir / "Resource"
    if not resource_root.is_dir():
        return prepared

    for path in resource_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".tga", ".qda", ".bmp"}:
            continue
        if path.name == "manifest.csv":
            continue
        relative = path.relative_to(resource_root)
        if relative.parts and relative.parts[0] != "Interface":
            continue
        archive_path = ("Resource/" + relative.as_posix()).replace("/", "\\")
        prepared[archive_path] = (path, _prepare_deploy_bytes(path, path.read_bytes()))
    return prepared


def deploy_pak_fallback_overrides(
    game_dir: Path,
    overrides_dir: Path,
    *,
    pak_path: Path | None = None,
) -> list[str]:
    """Inject nested Interface overrides into the pak when they differ from retail.

    Shallow paths (e.g. Main menu/fon.tga) are deployed loose only; ScummVM
    SearchMan can read them directly. Button QDAs under exit/, load/, etc. are
    one level too deep and must live in resource0.pak.
    """
    pak = pak_path or (game_dir / "Resource" / "resource0.pak")
    if not pak.exists():
        raise FileNotFoundError(f"Missing {pak}")

    import zipfile

    pending: dict[str, bytes] = {}
    with zipfile.ZipFile(pak, "r") as archive:
        members = {decode_pak_path(name).replace("\\", "/").lower(): name for name in archive.namelist()}
        for archive_path, (_source, data) in _interface_override_sources(overrides_dir).items():
            relative = Path(archive_path.replace("\\", "/"))
            if scummvm_loose_visible(relative):
                continue
            key = archive_path.replace("\\", "/").lower()
            member = members.get(key)
            if member and archive.read(member) == data:
                continue
            pending[archive_path] = data

    if not pending:
        return []

    print(
        f"  pak inject: {len(pending)} nested Interface override(s) "
        f"(may take 1-3 minutes)"
    )
    inject_files(pak, pending)
    return sorted(decode_pak_path(path) for path in pending)


def deploy_metadata(game_dir: Path, marker_path: Path, readme_path: Path) -> list[Path]:
    deployed: list[Path] = []
    if marker_path.exists():
        target = game_dir / marker_path.name
        shutil.copy2(marker_path, target)
        deployed.append(target)
    if readme_path.exists():
        target = game_dir / "readme.txt"
        shutil.copy2(readme_path, target)
        deployed.append(target)
    return deployed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--btdb", type=Path, default=DEFAULT_BTDB)
    parser.add_argument("--graphics-only", action="store_true")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--ini", type=Path, default=DEFAULT_INI)
    parser.add_argument("--skip-ini", action="store_true")
    parser.add_argument("--marker", type=Path, default=DEFAULT_MARKER)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--skip-scummvm", action="store_true")
    args = parser.parse_args()

    if not args.game_dir.exists():
        raise SystemExit(f"Game folder not found: {args.game_dir}")

    if args.graphics_only and args.text_only:
        raise SystemExit("Choose at most one of --graphics-only or --text-only.")

    print(f"Deploying loose files into: {args.game_dir}")
    print("(ScummVM loads shallow paths loose; nested menu QDAs are injected into the pak.)")

    if not args.graphics_only:
        text_targets = deploy_text(args.game_dir, args.csv, args.btdb)
        for target in text_targets:
            print(f"  text: {target}")

        qml_target = deploy_qml_patch(
            args.game_dir,
            DEFAULT_QML_PATCH,
            args.game_dir / "qd_game.qml",
        )
        if qml_target:
            print(f"  script: {qml_target} (отработано -> отработан state fix)")

    if not args.text_only:
        cache_deployed = deploy_resource_loose_caches(
            args.game_dir,
            overrides_dir=args.overrides,
        )
        for folder, targets in sorted(cache_deployed.items()):
            label = folder
            if folder == INVENTORY_ITEMS_FOLDER:
                label = f"{folder} (inventory items / letters)"
            print(f"  cache/{label}: {len(targets)} file(s)")

        removed_nested = _prune_nested_interface_loose(args.game_dir)
        if removed_nested:
            print(f"  prune: removed {len(removed_nested)} nested Interface file(s) (pak-only)")

        deployed = deploy_tree(args.overrides, args.game_dir)
        if deployed:
            print(f"  graphics: {len(deployed)} override file(s)")
            for path in deployed:
                print(f"    {path.relative_to(args.game_dir)}")
        else:
            print(f"  graphics: none in {args.overrides}")

        injected = deploy_pak_fallback_overrides(args.game_dir, args.overrides)
        for archive_path in injected:
            print(f"    pak: {archive_path}")

    if not args.skip_ini:
        ini_target = deploy_ini(args.game_dir, args.ini)
        if ini_target:
            print(f"  ini: {ini_target} (language=english, voice_mode=original)")

    for target in deploy_metadata(args.game_dir, args.marker, args.readme):
        print(f"  meta: {target.relative_to(args.game_dir)}")

    if not args.skip_scummvm:
        scummvm_ini = configure_scummvm(args.game_dir.resolve())
        if scummvm_ini:
            print(f"  scummvm: {scummvm_ini} (description -> English, target shveik-ru)")

    print("Done. Launch in ScummVM.")


if __name__ == "__main__":
    main()