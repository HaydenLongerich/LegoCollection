"""Draw the BrickLedger logo and save it as PNG and multi-size ICO.

Run from the project root: python tools/make_logo.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

BACKGROUND = (13, 13, 15, 255)      # COLORS["paper"]
RING = (48, 48, 52, 255)            # COLORS["line"]
BRICK = (210, 255, 0, 255)          # COLORS["accent"]
BRICK_SIDE = (150, 184, 0, 255)
BRICK_TOP = (228, 255, 92, 255)
STUD_SHADOW = (120, 148, 0, 255)


def draw(size: int = 1024) -> Image.Image:
    scale = 4  # draw large, then downsample for smooth edges
    s = size * scale
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    u = s / 32  # grid unit

    # Rounded tile background.
    d.rounded_rectangle((u * 1, u * 1, u * 31, u * 31), radius=u * 7, fill=BACKGROUND,
                        outline=RING, width=int(u * 0.6))

    # Brick body (front face + darker right side for depth).
    left, right, top, bottom, depth = u * 6.5, u * 23.5, u * 13, u * 25, u * 2.5
    d.polygon([(right, top), (right + depth, top - depth), (right + depth, bottom - depth), (right, bottom)],
              fill=BRICK_SIDE)
    d.polygon([(left, top), (left + depth, top - depth), (right + depth, top - depth), (right, top)],
              fill=BRICK_TOP)
    d.rectangle((left, top, right, bottom), fill=BRICK)

    # Two studs on top.
    stud_w, stud_h = u * 5, u * 2.2
    for centre in (left + (right - left) * 0.27 + depth / 2, left + (right - left) * 0.73 + depth / 2):
        base_y = top - depth / 2
        x0, x1 = centre - stud_w / 2, centre + stud_w / 2
        d.rectangle((x0, base_y - stud_h, x1, base_y), fill=STUD_SHADOW)
        d.ellipse((x0, base_y - u * 0.9, x1, base_y + u * 0.9), fill=STUD_SHADOW)
        d.ellipse((x0, base_y - stud_h - u * 0.9, x1, base_y - stud_h + u * 0.9), fill=BRICK_TOP)

    # Ledger lines on the brick face.
    for row in (0.38, 0.62):
        y = top + (bottom - top) * row
        d.rounded_rectangle((left + u * 2.2, y - u * 0.45, right - u * 2.2, y + u * 0.45),
                            radius=u * 0.45, fill=BACKGROUND)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    logo = draw()
    logo.save(ASSETS / "brickledger.png", optimize=True)
    logo.save(ASSETS / "brickledger.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Saved", ASSETS / "brickledger.png", "and", ASSETS / "brickledger.ico")


if __name__ == "__main__":
    main()
