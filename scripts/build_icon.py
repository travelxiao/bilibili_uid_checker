"""生成 Bilibili 风格多尺寸 ICO（电视机 Logo）。"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZES = [256, 128, 64, 48, 32, 16]

PINK = "#FB7299"
BLUE = "#00A1D6"
WHITE = "#FFFFFF"


def _draw_tv(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = max(size // 10, 2)
    body = [m, int(size * 0.28), size - m, size - m]
    draw.rounded_rectangle(body, radius=max(size // 8, 3), fill=PINK)

    screen_m = int(size * 0.22)
    draw.rounded_rectangle(
        [screen_m, int(size * 0.38), size - screen_m, int(size * 0.82)],
        radius=max(size // 16, 2),
        fill=BLUE,
    )

    eye_r = max(size // 28, 1)
    cy = int(size * 0.58)
    cx1, cx2 = int(size * 0.38), int(size * 0.62)
    for cx in (cx1, cx2):
        draw.ellipse([cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r], fill=WHITE)

    ant_y = int(size * 0.22)
    draw.line([int(size * 0.35), ant_y, int(size * 0.42), int(size * 0.12)], fill=PINK, width=max(size // 32, 1))
    draw.line([int(size * 0.65), ant_y, int(size * 0.58), int(size * 0.12)], fill=PINK, width=max(size // 32, 1))
    return img


def main():
    ASSETS.mkdir(exist_ok=True)
    images = [_draw_tv(s) for s in SIZES]
    out = ASSETS / "app.ico"
    images[0].save(out, format="ICO", sizes=[(s, s) for s in SIZES])
    images[0].save(ASSETS / "app.png", format="PNG")
    print(f"written {out}")


if __name__ == "__main__":
    main()
