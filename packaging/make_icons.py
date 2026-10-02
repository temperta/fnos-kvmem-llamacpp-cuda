#!/usr/bin/env python3
"""Generate fnOS package icons: ICON.PNG (64x64), ICON_256.PNG (256x256),
and desktop entry icons app/ui/images/icon_64.png / icon_256.png."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent / "fnos"


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_icon(size: int) -> Image.Image:
    scale = 4  # supersample for smooth edges
    S = size * scale
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # rounded-rect mask
    radius = int(S * 0.225)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)

    # horizontal gradient indigo -> sky (built as a 1-D ramp then upscaled)
    c0, c1 = (49, 46, 129), (14, 165, 233)  # #312E81 -> #0EA5E9
    ramp = Image.new("RGB", (S * 2, 1))
    rpx = ramp.load()
    for i in range(S * 2):
        rpx[i, 0] = lerp(c0, c1, i / (2 * S))
    grad = ramp.resize((S, S), Image.BICUBIC)
    img.paste(grad, (0, 0), mask)

    # chip glyph: rounded square with pins, plus "KV" text
    d2 = ImageDraw.Draw(img)
    cx, cy = S // 2, int(S * 0.42)
    box = int(S * 0.30)
    # pins
    pin = S * 0.028
    for off in (-box * 0.55, 0, box * 0.55):
        d2.line([cx + off, cy - box - pin, cx + off, cy - box], fill=(255, 255, 255, 235), width=int(pin * 0.8))
        d2.line([cx + off, cy + box, cx + off, cy + box + pin], fill=(255, 255, 255, 235), width=int(pin * 0.8))
        d2.line([cx - box - pin, cy + off, cx - box, cy + off], fill=(255, 255, 255, 235), width=int(pin * 0.8))
        d2.line([cx + box, cy + off, cx + box + pin, cy + off], fill=(255, 255, 255, 235), width=int(pin * 0.8))
    d2.rounded_rectangle([cx - box, cy - box, cx + box, cy + box], radius=int(box * 0.32),
                         outline=(255, 255, 255, 245), width=int(S * 0.035))
    d2.rounded_rectangle([cx - box * 0.45, cy - box * 0.45, cx + box * 0.45, cy + box * 0.45],
                         radius=int(box * 0.2), fill=(255, 255, 255, 245))

    # KV text at bottom
    font_path = None
    for cand in (
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ):
        if Path(cand).exists():
            font_path = cand
            break
    if font_path:
        font = ImageFont.truetype(font_path, int(S * 0.26))
    else:
        font = ImageFont.load_default()
    text = "KV"
    bbox = d2.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d2.text((cx - tw / 2 - bbox[0], int(S * 0.62) - bbox[1]), text, font=font, fill=(255, 255, 255, 250))

    img = img.resize((size, size), Image.LANCZOS)
    # flatten to sRGB RGB PNG (fnOS wants sRGB; alpha kept as PNG RGBA is fine, but we keep alpha)
    return img


def main():
    out_dirs = [
        (ROOT, "ICON_256.PNG", 256),
        (ROOT, "ICON.PNG", 64),
        (ROOT / "app" / "ui" / "images", "icon_256.png", 256),
        (ROOT / "app" / "ui" / "images", "icon_64.png", 64),
    ]
    for d, name, size in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
        icon = make_icon(size)
        icon.save(d / name, "PNG")
        print(f"wrote {d / name}")


if __name__ == "__main__":
    sys.exit(main())
