"""Extract and rebuild QDA UI sprites using qdEngine's RLE format."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from PIL import Image

ALPHA_FLAG = 0x01
# Engine RLE alpha sprites use 0xFF in the high byte as the transparent sentinel
# (see gr_draw_sprite_rle.cpp: skips drawing when alpha byte == 255).
ENGINE_TRANSPARENT_PIXEL = 0xFF000000


@dataclass
class QdaFrame:
    frame_flags: int
    start_time: float
    frame_length: float
    canvas_w: int
    canvas_h: int
    picture_w: int
    picture_h: int
    offset_x: int
    offset_y: int
    format_id: int
    source_name: str
    flags: int
    alpha_flag: int
    compressed: int
    rle_header_offset: bytes = b""
    rle_data_offset: bytes = b""
    rle_header: bytes = b""
    rle_data: bytes = b""
    raw_data: bytes = b""


@dataclass
class QdaAnimation:
    version: int
    canvas_w: int
    canvas_h: int
    length: float
    animation_flags: int
    num_frames: int
    num_scales: int
    tile_flag: int
    scales: list[float] = field(default_factory=list)
    frames: list[QdaFrame] = field(default_factory=list)


def _read_sprite_payload(data: bytes, offset: int, frame: QdaFrame, version: int) -> int:
    if not frame.compressed:
        bpp = {0: 2, 1: 2, 2: 3, 3: 4}.get(frame.format_id, 3)
        size = frame.picture_w * frame.picture_h * bpp
        if version < 102 and frame.alpha_flag:
            size += frame.picture_w * frame.picture_h
        frame.raw_data = data[offset : offset + size]
        return offset + size

    header_count, data_count, header_size, payload_size = struct.unpack_from("<4i", data, offset)
    offset += 16
    frame.rle_header_offset = data[offset : offset + header_count * 4]
    offset += header_count * 4
    frame.rle_data_offset = data[offset : offset + data_count * 4]
    offset += data_count * 4
    frame.rle_header = data[offset : offset + header_size]
    offset += header_size
    frame.rle_data = data[offset : offset + payload_size * 4]
    return offset + payload_size * 4


def parse_qda(data: bytes) -> QdaAnimation:
    offset = 0
    version, canvas_w, canvas_h = struct.unpack_from("<3i", data, offset)
    offset += 12
    length = struct.unpack_from("<f", data, offset)[0]
    offset += 4
    animation_flags, num_frames = struct.unpack_from("<2i", data, offset)
    offset += 8

    num_scales = 0
    if version >= 103:
        num_scales = struct.unpack_from("<i", data, offset)[0]
        offset += 4

    tile_flag = 0
    if version >= 104:
        tile_flag = struct.unpack_from("<b", data, offset)[0]
        offset += 1

    if tile_flag:
        raise ValueError("Tile animations are not supported")

    scales: list[float] = []
    if num_scales:
        scales = list(struct.unpack_from(f"<{num_scales}f", data, offset))
        offset += 4 * num_scales

    frames: list[QdaFrame] = []
    for _ in range(num_frames):
        frame_flags = struct.unpack_from("<i", data, offset)[0]
        offset += 4
        start_time, frame_length = struct.unpack_from("<2f", data, offset)
        offset += 8

        size_x, size_y, picture_w, picture_h, offset_x, offset_y = struct.unpack_from(
            "<6i", data, offset
        )
        offset += 24
        format_id, name_len = struct.unpack_from("<2i", data, offset)
        offset += 8

        source_name = data[offset : offset + name_len].split(b"\x00", 1)[0].decode("cp1251")
        offset += name_len

        flags, alpha_flag, compressed = struct.unpack_from("<3i", data, offset)
        offset += 12

        frame = QdaFrame(
            frame_flags=frame_flags,
            start_time=start_time,
            frame_length=frame_length,
            canvas_w=size_x,
            canvas_h=size_y,
            picture_w=picture_w,
            picture_h=picture_h,
            offset_x=offset_x,
            offset_y=offset_y,
            format_id=format_id,
            source_name=source_name,
            flags=flags,
            alpha_flag=alpha_flag,
            compressed=compressed,
        )
        offset = _read_sprite_payload(data, offset, frame, version)
        frames.append(frame)

    if num_scales:
        for _ in range(num_frames * num_scales):
            frame_flags = struct.unpack_from("<i", data, offset)[0]
            offset += 4
            start_time, frame_length = struct.unpack_from("<2f", data, offset)
            offset += 8
            size_x, size_y, picture_w, picture_h, offset_x, offset_y = struct.unpack_from(
                "<6i", data, offset
            )
            offset += 24
            format_id, name_len = struct.unpack_from("<2i", data, offset)
            offset += 8
            offset += name_len
            offset += 12
            skip = QdaFrame(
                frame_flags=frame_flags,
                start_time=start_time,
                frame_length=frame_length,
                canvas_w=size_x,
                canvas_h=size_y,
                picture_w=picture_w,
                picture_h=picture_h,
                offset_x=offset_x,
                offset_y=offset_y,
                format_id=format_id,
                source_name="",
                flags=0,
                alpha_flag=0,
                compressed=1,
            )
            offset = _read_sprite_payload(data, offset, skip, version)

    if offset != len(data):
        raise ValueError(f"QDA parse size mismatch: consumed {offset}, file has {len(data)}")

    return QdaAnimation(
        version=version,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        length=length,
        animation_flags=animation_flags,
        num_frames=num_frames,
        num_scales=num_scales,
        tile_flag=tile_flag,
        scales=scales,
        frames=frames,
    )


def _line_header_length(header: bytes, header_offsets: list[int], line: int) -> int:
    if line < len(header_offsets) - 1:
        return header_offsets[line + 1] - header_offsets[line]
    return len(header) - header_offsets[line]


def _engine_pixel_to_rgba(pixel: int, *, use_alpha_channel: bool) -> tuple[int, int, int, int]:
    if pixel == 0:
        return (0, 0, 0, 0)

    b = pixel & 0xFF
    g = (pixel >> 8) & 0xFF
    r = (pixel >> 16) & 0xFF
    if not use_alpha_channel:
        return (r, g, b, 255)

    engine_alpha = (pixel >> 24) & 0xFF
    png_alpha = 255 - engine_alpha
    if png_alpha == 0:
        return (0, 0, 0, 0)
    return (r, g, b, png_alpha)


def _rgba_to_engine_pixel(r: int, g: int, b: int, a: int, *, use_alpha_channel: bool) -> int:
    if a == 0:
        if use_alpha_channel:
            return ENGINE_TRANSPARENT_PIXEL
        return 0
    if not use_alpha_channel:
        return b | (g << 8) | (r << 16)
    engine_alpha = 255 - a
    return b | (g << 8) | (r << 16) | (engine_alpha << 24)


def decode_rle_frame(frame: QdaFrame) -> Image.Image:
    if not frame.compressed:
        raise ValueError("Only compressed (RLE) QDA sprites are supported")

    header_offsets = list(struct.unpack(f"<{len(frame.rle_header_offset) // 4}i", frame.rle_header_offset))
    data_offsets = list(struct.unpack(f"<{len(frame.rle_data_offset) // 4}i", frame.rle_data_offset))
    header = frame.rle_header
    payload = frame.rle_data
    use_alpha_channel = bool(frame.flags & ALPHA_FLAG)

    picture = Image.new("RGBA", (frame.picture_w, frame.picture_h), (0, 0, 0, 0))
    px = picture.load()

    for y in range(frame.picture_h):
        header_ptr = header_offsets[y]
        data_index = data_offsets[y] * 4
        header_len = _line_header_length(header, header_offsets, y)
        x = 0
        for _ in range(header_len):
            count = struct.unpack_from("<b", header, header_ptr)[0]
            header_ptr += 1
            if count > 0:
                pixel = struct.unpack_from("<I", payload, data_index)[0]
                data_index += 4
                rgba = _engine_pixel_to_rgba(pixel, use_alpha_channel=use_alpha_channel)
                for _repeat in range(count):
                    if x < frame.picture_w:
                        px[x, y] = rgba
                    x += 1
            else:
                run = -count
                for _run in range(run):
                    pixel = struct.unpack_from("<I", payload, data_index)[0]
                    data_index += 4
                    if x < frame.picture_w:
                        px[x, y] = _engine_pixel_to_rgba(pixel, use_alpha_channel=use_alpha_channel)
                    x += 1

    canvas = Image.new("RGBA", (frame.canvas_w, frame.canvas_h), (0, 0, 0, 0))
    canvas.paste(picture, (frame.offset_x, frame.offset_y))
    return canvas


def encode_rle(image: Image.Image, *, use_alpha_channel: bool) -> tuple[bytes, bytes, bytes, bytes]:
    width, height = image.size
    pixels = image.convert("RGBA").load()

    header_offsets: list[int] = []
    data_offsets: list[int] = []
    header = bytearray()
    data: list[int] = []

    for y in range(height):
        header_offsets.append(len(header))
        data_offsets.append(len(data))
        x = 0
        while x < width:
            r, g, b, a = pixels[x, y]
            pixel = _rgba_to_engine_pixel(r, g, b, a, use_alpha_channel=use_alpha_channel)
            run = 1
            while x + run < width and run < 127:
                rr, gg, bb, aa = pixels[x + run, y]
                other = _rgba_to_engine_pixel(rr, gg, bb, aa, use_alpha_channel=use_alpha_channel)
                if other != pixel:
                    break
                run += 1
            if run > 1:
                header += struct.pack("<b", run)
                data.append(pixel)
                x += run
                continue

            start = x
            x += 1
            while x < width and (x - start) < 127:
                rr, gg, bb, aa = pixels[x, y]
                cur = _rgba_to_engine_pixel(rr, gg, bb, aa, use_alpha_channel=use_alpha_channel)
                rr2, gg2, bb2, aa2 = pixels[x - 1, y]
                prev = _rgba_to_engine_pixel(rr2, gg2, bb2, aa2, use_alpha_channel=use_alpha_channel)
                if cur == prev:
                    break
                x += 1
            raw_len = x - start
            header += struct.pack("<b", -raw_len)
            for xx in range(start, x):
                rr, gg, bb, aa = pixels[xx, y]
                data.append(_rgba_to_engine_pixel(rr, gg, bb, aa, use_alpha_channel=use_alpha_channel))

    return (
        struct.pack(f"<{len(header_offsets)}i", *header_offsets),
        struct.pack(f"<{len(data_offsets)}i", *data_offsets),
        bytes(header),
        struct.pack(f"<{len(data)}I", *data),
    )


def _animation_header(animation: QdaAnimation) -> bytes:
    parts = [
        struct.pack("<3i", animation.version, animation.canvas_w, animation.canvas_h),
        struct.pack("<f", animation.length),
        struct.pack("<2i", animation.animation_flags, animation.num_frames),
    ]
    if animation.version >= 103:
        parts.append(struct.pack("<i", animation.num_scales))
        if animation.scales:
            parts.append(struct.pack(f"<{len(animation.scales)}f", *animation.scales))
    if animation.version >= 104:
        parts.append(struct.pack("<b", animation.tile_flag))
    return b"".join(parts)


def _frame_prefix(frame: QdaFrame) -> bytes:
    return b"".join(
        [
            struct.pack("<i", frame.frame_flags),
            struct.pack("<2f", frame.start_time, frame.frame_length),
            struct.pack(
                "<8i",
                frame.canvas_w,
                frame.canvas_h,
                frame.picture_w,
                frame.picture_h,
                frame.offset_x,
                frame.offset_y,
                frame.format_id,
                len(frame.source_name),
            ),
            frame.source_name.encode("cp1251"),
            struct.pack("<3i", frame.flags, frame.alpha_flag, frame.compressed),
        ]
    )


def qda_to_png(data: bytes, output: Path, *, frame_index: int = 0) -> QdaAnimation:
    animation = parse_qda(data)
    if frame_index >= len(animation.frames):
        raise ValueError(f"Frame {frame_index} unavailable (has {len(animation.frames)})")
    image = decode_rle_frame(animation.frames[frame_index])
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return animation


def qda_to_pngs(data: bytes, output: Path) -> QdaAnimation:
    animation = parse_qda(data)
    if len(animation.frames) == 1:
        qda_to_png(data, output, frame_index=0)
        return animation

    stem = output.stem
    suffix = output.suffix
    for index, _frame in enumerate(animation.frames):
        frame_path = output.with_name(f"{stem}_f{index:02d}{suffix}")
        qda_to_png(data, frame_path, frame_index=index)
    return animation


def _apply_png_to_frame(frame: QdaFrame, png_path: Path) -> None:
    image = Image.open(png_path).convert("RGBA")
    expected = (frame.canvas_w, frame.canvas_h)
    if image.size != expected:
        print(
            f"warning: {png_path.name} is {image.size[0]}x{image.size[1]}, "
            f"resizing to {expected[0]}x{expected[1]} for QDA import"
        )
        image = image.resize(expected, Image.Resampling.LANCZOS)

    crop = image.crop(
        (
            frame.offset_x,
            frame.offset_y,
            frame.offset_x + frame.picture_w,
            frame.offset_y + frame.picture_h,
        )
    )
    header_offset, data_offset, header, payload = encode_rle(
        crop,
        use_alpha_channel=bool(frame.flags & ALPHA_FLAG),
    )
    frame.rle_header_offset = header_offset
    frame.rle_data_offset = data_offset
    frame.rle_header = header
    frame.rle_data = payload


def _write_frame(out: BytesIO, frame: QdaFrame) -> None:
    out.write(_frame_prefix(frame))
    out.write(struct.pack("<i", len(frame.rle_header_offset) // 4))
    out.write(struct.pack("<i", len(frame.rle_data_offset) // 4))
    out.write(struct.pack("<i", len(frame.rle_header)))
    out.write(struct.pack("<i", len(frame.rle_data) // 4))
    out.write(frame.rle_header_offset)
    out.write(frame.rle_data_offset)
    out.write(frame.rle_header)
    out.write(frame.rle_data)


def _scaled_frame_blob(data: bytes, offset: int, version: int) -> tuple[bytes, int]:
    frame_flags = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    start_time, frame_length = struct.unpack_from("<2f", data, offset)
    offset += 8
    size_x, size_y, picture_w, picture_h, offset_x, offset_y = struct.unpack_from("<6i", data, offset)
    offset += 24
    format_id, name_len = struct.unpack_from("<2i", data, offset)
    offset += 8
    source_name = data[offset : offset + name_len]
    offset += name_len
    flags, alpha_flag, compressed = struct.unpack_from("<3i", data, offset)
    offset += 12

    frame = QdaFrame(
        frame_flags=frame_flags,
        start_time=start_time,
        frame_length=frame_length,
        canvas_w=size_x,
        canvas_h=size_y,
        picture_w=picture_w,
        picture_h=picture_h,
        offset_x=offset_x,
        offset_y=offset_y,
        format_id=format_id,
        source_name=source_name.split(b"\x00", 1)[0].decode("cp1251"),
        flags=flags,
        alpha_flag=alpha_flag,
        compressed=compressed,
    )
    start = offset
    offset = _read_sprite_payload(data, offset, frame, version)
    return data[start - (4 + 8 + 24 + 8 + name_len + 12) : offset], offset


def png_to_qda(original: bytes, png_path: Path, *, frame_index: int = 0) -> bytes:
    animation = parse_qda(original)
    if frame_index >= len(animation.frames):
        raise ValueError(f"Frame {frame_index} unavailable (has {len(animation.frames)})")

    _apply_png_to_frame(animation.frames[frame_index], png_path)

    out = BytesIO()
    out.write(_animation_header(animation))

    for frame in animation.frames:
        _write_frame(out, frame)

    if animation.num_scales:
        offset = 0
        version = animation.version
        data = original
        offset = 12 + 4 + 8
        if version >= 103:
            offset += 4
        if version >= 104:
            offset += 1
        if animation.scales:
            offset += 4 * len(animation.scales)
        for _ in animation.frames:
            frame_flags = struct.unpack_from("<i", data, offset)[0]
            offset += 4
            offset += 8
            _, _, _, _, _, _, _, name_len = struct.unpack_from("<8i", data, offset)
            offset += 32 + name_len + 12
            hc, dc, hs, ds = struct.unpack_from("<4i", data, offset)
            offset += 16 + hc * 4 + dc * 4 + hs + ds * 4

        for _ in range(animation.num_frames * animation.num_scales):
            blob, offset = _scaled_frame_blob(data, offset, version)
            out.write(blob)

    return out.getvalue()


def _base_png_stem(stem: str) -> str:
    if len(stem) > 4 and stem[-4] == "_" and stem[-3] == "f" and stem[-2:].isdigit():
        return stem[:-4]
    return stem


def pngs_to_qda(original: bytes, png_path: Path) -> bytes:
    animation = parse_qda(original)
    if len(animation.frames) == 1:
        return png_to_qda(original, png_path, frame_index=0)

    stem = _base_png_stem(png_path.stem)
    suffix = png_path.suffix
    for index in range(len(animation.frames)):
        frame_path = png_path.with_name(f"{stem}_f{index:02d}{suffix}")
        if not frame_path.exists():
            raise FileNotFoundError(f"Missing edited frame: {frame_path}")
        _apply_png_to_frame(animation.frames[index], frame_path)

    return png_to_qda(original, png_path, frame_index=0)