"""Draw the big green README download button (assets/download-button.png).

Run from the project root: python tools/make_download_button.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "download-button.png"

GREEN = (35, 134, 54, 255)       # GitHub's own "Code" button green
GREEN_EDGE = (46, 160, 67, 255)
WHITE = (255, 255, 255, 255)
SUBTLE = (214, 240, 219, 255)


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    names = ("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def main() -> None:
    scale = 2  # draw at 2x so it stays crisp on high-DPI screens
    width, height = 460 * scale, 96 * scale
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((0, 0, width - 1, height - 1), radius=18 * scale, fill=GREEN,
                        outline=GREEN_EDGE, width=2 * scale)

    # Download arrow icon.
    cx, cy, u = 62 * scale, height // 2, scale
    d.rounded_rectangle((cx - 4 * u, cy - 24 * u, cx + 4 * u, cy + 4 * u), radius=3 * u, fill=WHITE)
    d.polygon([(cx - 15 * u, cy - 2 * u), (cx + 15 * u, cy - 2 * u), (cx, cy + 14 * u)], fill=WHITE)
    d.rounded_rectangle((cx - 20 * u, cy + 18 * u, cx + 20 * u, cy + 24 * u), radius=3 * u, fill=WHITE)

    left = 106 * scale
    d.text((left, 18 * scale), "Download BrickLedger", font=font(True, 30 * scale), fill=WHITE)
    d.text((left, 56 * scale), "Windows  ·  v1.0.0 beta  ·  30 MB", font=font(False, 17 * scale), fill=SUBTLE)

    image.save(OUTPUT, optimize=True)
    print("Saved", OUTPUT)


if __name__ == "__main__":
    main()
