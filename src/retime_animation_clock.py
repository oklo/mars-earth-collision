#!/usr/bin/env python3
"""Replace the elapsed-time clock in a fixed-duration movie with civil time."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BACKGROUND = "0x03050a"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/SFNS.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--frames", type=int, default=720)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--sim-hours", type=float, default=4.0)
    parser.add_argument("--month", type=int, default=8)
    parser.add_argument("--day", type=int, default=17)
    parser.add_argument("--hour", type=int, default=10)
    parser.add_argument("--minute", type=int, default=0)
    parser.add_argument("--zone", default="MDT")
    parser.add_argument("--font-size", type=int, default=25)
    parser.add_argument(
        "--font-path",
        type=Path,
        default=None,
        help="TrueType/OpenType font; defaults to SF Pro, DejaVu Sans, or Pillow's fallback",
    )
    parser.add_argument("--clear-x", type=int, default=20)
    parser.add_argument("--clear-y", type=int, default=68)
    parser.add_argument("--clear-width", type=int, default=560)
    parser.add_argument("--clear-height", type=int, default=78)
    parser.add_argument("--text-x", type=int, default=48)
    parser.add_argument("--text-y", type=int, default=94)
    return parser.parse_args()


def clock_text(when: datetime, zone: str) -> str:
    hour = when.hour % 12 or 12
    meridiem = "AM" if when.hour < 12 else "PM"
    return f"{when:%b} {when.day}, {hour}:{when.minute:02d} {meridiem} {zone}"


def render_overlays(
    directory: Path,
    frames: int,
    start: datetime,
    sim_hours: float,
    zone: str,
    font_size: int,
    font_path: Path | None,
) -> None:
    if font_path is not None:
        font = ImageFont.truetype(str(font_path), font_size)
    else:
        font = None
        for candidate in FONT_CANDIDATES:
            if candidate.is_file():
                font = ImageFont.truetype(str(candidate), font_size)
                break
        if font is None:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except OSError:
                font = ImageFont.load_default(size=font_size)
    for index in range(frames):
        fraction = index / max(frames - 1, 1)
        when = start + timedelta(hours=sim_hours * fraction)
        image = Image.new("RGBA", (500, 80), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), clock_text(when, zone), font=font, fill=(170, 179, 193, 255))
        image.save(directory / f"clock_{index:04d}.png")


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input movie not found: {args.input}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2000, args.month, args.day, args.hour, args.minute)

    with tempfile.TemporaryDirectory(prefix="retime_clock_") as temp_name:
        temp_dir = Path(temp_name)
        render_overlays(
            temp_dir,
            args.frames,
            start,
            args.sim_hours,
            args.zone,
            args.font_size,
            args.font_path,
        )
        filter_graph = (
            f"[0:v]drawbox=x={args.clear_x}:y={args.clear_y}:"
            f"w={args.clear_width}:h={args.clear_height}:"
            f"color={BACKGROUND}:t=fill[clean];"
            f"[clean][1:v]overlay=x={args.text_x}:y={args.text_y}:shortest=1[v]"
        )
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(args.input),
            "-framerate",
            str(args.fps),
            "-i",
            str(temp_dir / "clock_%04d.png"),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(args.output),
        ]
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
