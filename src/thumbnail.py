"""
Makes a YouTube thumbnail (1280x720 JPEG) from a frame of the footage.

Designed for older eyes: a dimmed calm image, a big cream-coloured serif title
with a dark outline, a small "SLEEP STORY" label and the story length.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from src.media import duration_seconds, run

WIDTH, HEIGHT = 1280, 720
CREAM = (242, 233, 208)
GREEN = (143, 209, 168)
NAVY = (20, 26, 51)

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
    "C:/Windows/Fonts/timesbd.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
)


def _font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    try:  # Pillow 10.1+ can scale its built-in font
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _extract_frame(video: str, dest: Path):
    seconds = max(1.0, min(25.0, duration_seconds(video) / 2))
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seconds:.1f}",
         "-i", video, "-frames:v", "1", "-q:v", "2", str(dest)],
        what="grab thumbnail frame",
    )


def _cover(image: Image.Image) -> Image.Image:
    scale = max(WIDTH / image.width, HEIGHT / image.height)
    image = image.resize((int(image.width * scale) + 1, int(image.height * scale) + 1))
    left = (image.width - WIDTH) // 2
    top = (image.height - HEIGHT) // 2
    return image.crop((left, top, left + WIDTH, top + HEIGHT))


def _wrap(draw, text: str, font, max_width: int):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_thumbnail(video: str, title: str, minutes: int, workdir: str) -> str:
    work = Path(workdir)
    frame_path = work / "thumb_frame.jpg"
    _extract_frame(video, frame_path)

    image = _cover(Image.open(frame_path).convert("RGB"))
    image = ImageEnhance.Brightness(image).enhance(0.62)
    image = ImageEnhance.Color(image).enhance(0.9)

    # Darker band on the left and bottom so the text stays readable.
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for x in range(WIDTH):
        alpha = int(150 * max(0.0, 1 - x / (WIDTH * 0.85)))
        odraw.line([(x, 0), (x, HEIGHT)], fill=(*NAVY, alpha))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(image)
    margin, max_width = 70, 960

    # Shrink the title until it fits in at most three lines.
    size, lines = 140, []
    while size >= 70:
        font = _font(size)
        lines = _wrap(draw, title, font, max_width)
        if len(lines) <= 3:
            break
        size -= 10
    line_height = int(size * 1.12)
    block_height = line_height * len(lines)
    y = (HEIGHT - block_height) // 2 + 10
    for line in lines:
        draw.text((margin, y), line, font=font, fill=CREAM,
                  stroke_width=max(4, size // 18), stroke_fill=NAVY)
        y += line_height

    label_font = _font(46)
    draw.text((margin, 60), "SLEEP STORY", font=label_font, fill=GREEN,
              stroke_width=3, stroke_fill=NAVY)

    pill_text = f"{minutes} MIN"
    pill_font = _font(50)
    text_w = draw.textlength(pill_text, font=pill_font)
    x0, y0 = margin, HEIGHT - 120
    draw.rounded_rectangle((x0, y0, x0 + text_w + 56, y0 + 76), radius=38, fill=NAVY)
    draw.text((x0 + 28, y0 + 8), pill_text, font=pill_font, fill=CREAM)

    out = work / "thumbnail.jpg"
    for quality in (90, 82, 74, 66):  # YouTube's limit is 2 MB
        image.save(out, "JPEG", quality=quality, optimize=True)
        if out.stat().st_size < 1_900_000:
            break
    return str(out)
