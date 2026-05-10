#!/usr/bin/env python3
"""Generate windows/ragsnip.ico — a multi-resolution Windows icon.

Design: rounded-square accent-blue background with white selection
brackets at the four corners (the visual cue for "region snipping")
and a small focus dot in the centre. Each size is rendered at native
resolution rather than down-scaled, so 16×16 stays sharp.

Run from the repo root or windows/ — output is windows/ragsnip.ico.
"""

from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "ragsnip.ico"
SIZES = [256, 128, 64, 48, 32, 16]
ACCENT = (59, 130, 246, 255)   # matches GUI Accent colour
WHITE = (255, 255, 255, 255)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background — rounded square in accent blue
    radius = max(2, int(round(size * 0.22)))
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=ACCENT,
    )

    # Selection brackets at the four corners
    margin = max(2, int(round(size * 0.22)))
    bracket_len = max(2, int(round(size * 0.18)))
    stroke = max(1, int(round(size * 0.06)))

    x1, y1 = margin, margin
    x2, y2 = size - 1 - margin, size - 1 - margin

    # top-left
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=WHITE, width=stroke)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=WHITE, width=stroke)
    # top-right
    draw.line([(x2, y1), (x2 - bracket_len, y1)], fill=WHITE, width=stroke)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=WHITE, width=stroke)
    # bottom-left
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=WHITE, width=stroke)
    draw.line([(x1, y2), (x1, y2 - bracket_len)], fill=WHITE, width=stroke)
    # bottom-right
    draw.line([(x2, y2), (x2 - bracket_len, y2)], fill=WHITE, width=stroke)
    draw.line([(x2, y2), (x2, y2 - bracket_len)], fill=WHITE, width=stroke)

    # Focus dot in the centre — only at sizes large enough to show it cleanly
    if size >= 32:
        cx, cy = size // 2, size // 2
        dot_r = max(1, int(round(size * 0.06)))
        draw.ellipse(
            [(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)],
            fill=WHITE,
        )

    return img


def main() -> None:
    images = [render(s) for s in SIZES]
    # Pillow saves multi-resolution ICO when given append_images plus
    # a sizes= manifest. Each image must already be the right size.
    images[0].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[1:],
    )
    print(f"Wrote {OUT} ({len(SIZES)} resolutions)")


if __name__ == "__main__":
    main()
