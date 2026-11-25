"""Convert TGAs to the format the QD engine expects (type 2, uncompressed)."""

from __future__ import annotations

import struct
from pathlib import Path


def _decode_rle(payload: bytes, width: int, height: int, bpp: int) -> bytes:
    col = bpp // 8
    need = width * height * col
    out = bytearray()
    i = 0
    while len(out) < need and i < len(payload):
        info = payload[i]
        i += 1
        repeat = (info >> 7) & 1
        count = (info & 0x7F) + 1
        if repeat:
            pixel = payload[i : i + col]
            i += col
            out.extend(pixel * count)
        else:
            chunk = payload[i : i + count * col]
            i += count * col
            out.extend(chunk)
    if len(out) != need:
        raise ValueError(f"RLE decode failed: got {len(out)} bytes, expected {need}")
    return bytes(out)


def ensure_engine_tga(data: bytes, source: Path | None = None) -> bytes:
    """Return an uncompressed true-color TGA (type 2), matching retail assets."""
    if len(data) < 18:
        raise ValueError(f"TGA too small: {source}")

    header = bytearray(data[:18])
    image_type = header[2]
    id_len = header[0]
    width = struct.unpack_from("<H", header, 12)[0]
    height = struct.unpack_from("<H", header, 14)[0]
    bpp = header[16]

    if bpp not in (24, 32):
        raise ValueError(f"Unsupported TGA bpp={bpp} in {source}")

    offset = 18 + id_len
    payload = data[offset:]

    if image_type == 2:
        need = width * height * (bpp // 8)
        if len(payload) < need:
            raise ValueError(f"Truncated uncompressed TGA: {source}")
        return data

    if image_type != 10:
        raise ValueError(f"Unsupported TGA type {image_type} in {source}")

    pixels = _decode_rle(payload, width, height, bpp)
    header[2] = 2
    return bytes(header) + pixels


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()

    output = args.output or args.input
    converted = ensure_engine_tga(args.input.read_bytes(), args.input)
    output.write_bytes(converted)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()