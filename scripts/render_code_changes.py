#!/usr/bin/env python3
"""Build an animated GIF from the actual line-change values in Metrics SVG."""
import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 760, 252
BACKGROUND = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
FOREGROUND = "#e6edf3"
MUTED = "#8b949e"
GREEN = "#3fb950"
RED = "#f85149"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def parse_number(raw):
    factor = {"k": 1_000, "m": 1_000_000}
    return round(float(raw.rstrip("kKmM").replace(",", "")) * factor.get(raw[-1:].lower(), 1))


def compact(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if value >= 10_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{value:,}"


def read_data(path):
    svg = Path(path).read_text(encoding="utf-8")
    match = re.search(r"([\d,.]+[kKmM]?)\s+added,\s+([\d,.]+[kKmM]?)\s+removed", svg)
    if not match:
        raise ValueError("Metrics SVG has no valid added/removed totals: cannot draw actual statistics")
    repos = re.search(r"(\d+)\s+Repositories", svg)
    return parse_number(match.group(1)), parse_number(match.group(2)), (
        int(repos.group(1)) if repos else None
    )


def render_frame(added, removed, repositories, fraction):
    eased = 1 - (1 - fraction) ** 3
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, WIDTH - 2, HEIGHT - 2), radius=15,
                           fill=PANEL, outline=BORDER, width=2)
    draw.rounded_rectangle((25, 24, 30, 51), radius=2, fill=GREEN)
    draw.text((45, 21), "CODE CHANGES", font=font(22, True), fill=FOREGROUND)

    if repositories is not None:
        caption = f"{repositories} repositories"
        length = draw.textlength(caption, font=font(14))
        draw.text((WIDTH - 28 - length, 29), caption, font=font(14), fill=MUTED)

    maximum = max(added, removed, 1)
    for x, label, quantity, color, sign in [
        (36, "LINES ADDED", added, GREEN, "+"),
        (396, "LINES REMOVED", removed, RED, "-"),
    ]:
        draw.text((x, 80), label, font=font(15, True), fill=MUTED)
        number = sign + compact(round(quantity * eased))
        draw.text((x, 110), number, font=font(43, True), fill=color)
        y = 191
        draw.rounded_rectangle((x, y, x + 308, y + 17), radius=8, fill=BACKGROUND)
        extent = round(308 * quantity / maximum * eased)
        if extent > 0:
            draw.rounded_rectangle((x, y, x + extent, y + 17),
                                   radius=min(8, max(0, extent // 2)), fill=color)
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="metrics.plugin.lines.svg")
    parser.add_argument("--output", default="metrics.plugin.lines.gif")
    args = parser.parse_args()

    added, removed, repositories = read_data(args.input)
    frames = [
        render_frame(added, removed, repositories, index / 20).quantize(colors=96)
        for index in range(21)
    ]
    frames.extend(frames[-1].copy() for _ in range(5))
    durations = [65] * 20 + [90] + [240] * 5

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        args.output, format="GIF", save_all=True, append_images=frames[1:],
        duration=durations, optimize=True, disposal=2,
    )
    print(f"Generated animated card: +{added:,}, -{removed:,}, {repositories} repositories")


if __name__ == "__main__":
    main()
