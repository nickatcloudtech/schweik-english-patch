#!/usr/bin/env python3
"""Extract Schweik CD images and Inno Setup installer."""

import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CD1_ISO = os.path.join(ROOT, "Pohozhdeniya-bravogo-soldata-Shveyka_Win_RU_CD1", "Shveik_cd1.mdf")
CD2_ISO = os.path.join(ROOT, "Pohozhdeniya-bravogo-soldata-Shveyka_Win_RU_CD2", "Shveik_cd2.mdf")
INSTALLER_DIR = os.path.join(ROOT, "game", "installer")
GAME_DIR = os.path.join(ROOT, "game", "shveik")


class ISO9660:
    SECTOR = 2048

    def __init__(self, path):
        self.f = open(path, "rb")
        self.f.seek(16 * self.SECTOR)
        pvd = self.f.read(self.SECTOR)
        rr = pvd[156:190]
        self.root_loc = struct.unpack("<I", rr[2:6])[0]
        self.root_len = struct.unpack("<I", rr[10:14])[0]

    def read_dir(self, loc, length):
        self.f.seek(loc * self.SECTOR)
        data = self.f.read(length)
        entries = []
        off = 0
        while off < len(data):
            reclen = data[off]
            if reclen == 0:
                off = ((off // self.SECTOR) + 1) * self.SECTOR
                continue
            rec = data[off : off + reclen]
            ext_loc = struct.unpack("<I", rec[2:6])[0]
            ext_len = struct.unpack("<I", rec[10:14])[0]
            flags = rec[25]
            nlen = rec[32]
            name = rec[33 : 33 + nlen].decode("ascii", "replace").split(";")[0]
            entries.append(
                {
                    "name": name,
                    "loc": ext_loc,
                    "len": ext_len,
                    "dir": bool(flags & 0x02),
                }
            )
            off += reclen
        return entries

    def extract(self, loc, length, dest):
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as out:
            remaining = length
            sector = loc
            while remaining > 0:
                self.f.seek(sector * self.SECTOR)
                chunk = self.f.read(min(remaining, self.SECTOR))
                out.write(chunk)
                remaining -= len(chunk)
                sector += 1


def extract_iso(iso_path, files):
    iso = ISO9660(iso_path)
    root = iso.read_dir(iso.root_loc, iso.root_len)
    os.makedirs(INSTALLER_DIR, exist_ok=True)
    for entry in root:
        if entry["name"] in files and not entry["dir"]:
            dest = os.path.join(INSTALLER_DIR, entry["name"])
            print(f"Extracting {entry['name']} ({entry['len'] / 1e6:.0f} MB)...")
            iso.extract(entry["loc"], entry["len"], dest)


def prepare_inno_bins():
    mapping = {
        "SETUP_1.BIN": "setup-1.bin",
        "SETUP_2.BIN": "setup-2.bin",
    }
    for src, dst in mapping.items():
        src_path = os.path.join(INSTALLER_DIR, src)
        dst_path = os.path.join(INSTALLER_DIR, dst)
        if os.path.exists(src_path) and not os.path.exists(dst_path):
            os.link(src_path, dst_path)


def run_innoextract():
    os.makedirs(GAME_DIR, exist_ok=True)
    setup = os.path.join(INSTALLER_DIR, "SETUP.EXE")
    subprocess.run(
        ["innoextract", "-e", "--collisions", "overwrite", "-d", GAME_DIR, setup],
        cwd=INSTALLER_DIR,
        check=True,
    )


def main():
    extract_iso(CD1_ISO, ["SETUP.EXE", "SETUP_1.BIN"])
    extract_iso(CD2_ISO, ["SETUP_2.BIN"])
    prepare_inno_bins()
    run_innoextract()
    print(f"Game extracted to {GAME_DIR}")


if __name__ == "__main__":
    main()