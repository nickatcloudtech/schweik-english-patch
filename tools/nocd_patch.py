#!/usr/bin/env python3
"""Merge resource1.pak into resource0.pak so Schweik runs without the CD."""

import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "game", "shveik", "app")
RESOURCE = os.path.join(APP, "Resource")


def merge_paks():
    r0_path = os.path.join(RESOURCE, "resource0.pak")
    r1_path = os.path.join(RESOURCE, "resource1.pak")
    merged_path = os.path.join(RESOURCE, "resource0_merged.pak")

    if not os.path.exists(r0_path) or not os.path.exists(r1_path):
        raise SystemExit("Run extract_schweik.py first.")

    with zipfile.ZipFile(r0_path, "r") as z0:
        names0 = set(z0.namelist())
        print(f"resource0: {len(names0)} files")

    added = 0
    with zipfile.ZipFile(r0_path, "r") as z0, zipfile.ZipFile(r1_path, "r") as z1:
        with zipfile.ZipFile(merged_path, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for item in z0.infolist():
                out.writestr(item, z0.read(item.filename))
            for item in z1.infolist():
                if item.filename not in names0:
                    out.writestr(item, z1.read(item.filename))
                    added += 1

    print(f"Added {added} files from resource1")

    for path in (r0_path, r1_path):
        backup = path + ".bak"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)

    shutil.move(merged_path, r0_path)
    print("Merged archive installed as resource0.pak")
    print("Original paks saved as resource0.pak.bak and resource1.pak.bak")


if __name__ == "__main__":
    merge_paks()