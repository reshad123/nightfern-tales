"""
Makes the YouTube thumbnail (1280x720 JPEG), in the style of a night-time storybook cover:
a big cream serif title with a navy outline, an aqua "SLEEP STORY" label and a navy pill
with the story length.

Background, in order of preference:
  1. your own art for the story: assets/thumbs/<seed id>.jpg (or .png / .webp);
  2. otherwise a frame of the footage turned into a night scene, with a moon and stars.
"""

import itertools
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from config import THUMB_ART_DIR, THUMB_FONT
from src.media import duration_seconds, run

WIDTH, HEIGHT = 1280, 720
CREAM = (252, 244, 214)
NAVY = (12, 20, 48)
PILL = (14, 24, 56)
AQUA = (70, 226, 205)
MARGIN = 64
MAX_TITLE_WIDTH = int(WIDTH * 0.78)

FONT_FALLBACKS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
)


def _font(size: int):
    for path in (str(THUMB_FONT), *FONT_FALLBACKS):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def find_art(seed_id: str):
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidate = Path(THUMB_ART_DIR) / f"{seed_id}.{ext}"
        if candidate.is_file():
            return candidate
    return None


def _cover(image: Image.Image) -> Image.Image:
    scale = max(WIDTH / image.width, HEIGHT / image.height)
    image = image.resize((int(image.width * scale) + 1, int(image.height * scale) + 1),
                         Image.LANCZOS)
    left, top = (image.width - WIDTH) // 2, (image.height - HEIGHT) // 2
    return image.crop((left, top, left + WIDTH, top + HEIGHT))


def _extract_frame(video: str, dest: Path):
    seconds = max(1.0, min(25.0, duration_seconds(video) / 2))
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seconds:.1f}", "-i", video,
         "-frames:v", "1", "-q:v", "2", str(dest)],
        what="grab thumbnail frame",
    )


def _night_scene(frame: Image.Image, seed: str) -> Image.Image:
    """Turn a footage frame into a moonlit night picture (moon + stars)."""
    image = _cover(frame.convert("RGB"))
    image = ImageEnhance.Brightness(image).enhance(0.7)
    image = Image.blend(image, Image.new("RGB", image.size, (14, 28, 70)), 0.28)

    rng = random.Random(seed)
    draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(170):  # stars, thinning out towards the horizon
        x, y = rng.randint(0, WIDTH), int(HEIGHT * 0.62 * rng.random() ** 1.7)
        r, a = rng.choice((1, 1, 1, 2)), rng.randint(110, 235)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 250, 235, a))

    cx, cy, radius = int(WIDTH * 0.8), int(HEIGHT * 0.2), 48
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        (cx - radius * 2.4, cy - radius * 2.4, cx + radius * 2.4, cy + radius * 2.4),
        fill=(190, 210, 255, 135))
    glow = glow.filter(ImageFilter.GaussianBlur(radius * 1.2))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    moon = ImageDraw.Draw(image, "RGBA")
    moon.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 248, 225, 255))
    for dx, dy, r in ((-16, -10, 11), (14, 12, 9), (-4, 20, 6), (20, -18, 5)):  # soft craters
        moon.ellipse((cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r), fill=(204, 193, 160, 200))
    return image.convert("RGB")


LINK_WORDS = {"a", "an", "the", "of", "in", "on", "at", "by", "to", "for", "with", "and", "or",
              "through", "under", "beneath", "over", "into", "from", "near", "past", "across"}


def _penalty(lines):
    """Typographic cost of a set of line breaks (0 = ideal)."""
    cost = 0
    for line in lines[:-1]:
        if line.split()[-1].lower().strip(".,!?'") in LINK_WORDS:
            cost += 120  # a line should not end on 'through', 'of', 'the' ...
    if len(lines) > 1 and len(lines[-1].split()) == 1:
        cost += 40  # a lonely last word
    return cost


def _wrap_best(words, n_lines, measure, max_width):
    """Best way to split words into n lines that all fit: fewest typographic
    problems first, then the narrowest widest-line. None if nothing fits."""
    best, best_key = None, None
    for cuts in itertools.combinations(range(1, len(words)), n_lines - 1):
        bounds = (0, *cuts, len(words))
        lines = [" ".join(words[bounds[i]:bounds[i + 1]]) for i in range(n_lines)]
        width = max(measure(line) for line in lines)
        if width > max_width:
            continue
        key = (_penalty(lines), width)
        if best is None or key < best_key:
            best, best_key = lines, key
    return best, best_key


def fit_title(title: str, draw: ImageDraw.ImageDraw):
    """Pick the font size and line breaks. Big is good, but not at the price of an
    awkward break: each point of typographic penalty costs 0.2 points of font size."""
    words = title.split()
    best = None
    for size in range(140, 61, -4):
        font = _font(size)
        measure = lambda text: draw.textlength(text, font=font)
        options = []
        for n in range(1, min(3, len(words)) + 1):
            lines, key = _wrap_best(words, n, measure, MAX_TITLE_WIDTH)
            if lines:
                options.append((key, lines))
        if not options:
            continue
        (penalty, _), lines = min(options)
        score = size - 0.2 * penalty
        if best is None or score > best[0]:
            best = (score, size, lines)
    if best is None:
        return _font(62), 62, [title]
    _, size, lines = best
    return _font(size), size, lines


def _text_with_shadow(image: Image.Image, xy, text, font, fill, stroke):
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((xy[0], xy[1] + 7), text, font=font, fill=(0, 0, 0, 170),
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    image.paste(Image.alpha_composite(image.convert("RGBA"), shadow).convert("RGB"))
    ImageDraw.Draw(image).text(xy, text, font=font, fill=fill,
                               stroke_width=stroke, stroke_fill=NAVY)


def make_thumbnail(video: str, title: str, minutes: int, workdir: str, seed_id: str = "") -> str:
    work = Path(workdir)
    art = find_art(seed_id) if seed_id else None
    if art:
        image = _cover(Image.open(art).convert("RGB"))
        print(f"Thumbnail background: your art ({art.name})")
    else:
        frame = work / "thumb_frame.jpg"
        _extract_frame(video, frame)
        image = _night_scene(Image.open(frame), seed_id or title)
        print("Thumbnail background: night scene made from the footage "
              "(add art to assets/thumbs/ for a richer look)")

    # A soft darkening on the left so the title stays readable on any art.
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shade)
    for x in range(WIDTH):
        sdraw.line([(x, 0), (x, HEIGHT)], fill=(*NAVY, int(105 * max(0.0, 1 - x / (WIDTH * 0.8)))))
    image = Image.alpha_composite(image.convert("RGBA"), shade).convert("RGB")

    draw = ImageDraw.Draw(image)
    font, size, lines = fit_title(title, draw)
    stroke = max(5, size // 14)
    line_height = int(size * 1.08)
    top_limit, bottom_limit = 128, HEIGHT - 140
    y = top_limit + max(0, (bottom_limit - top_limit - line_height * len(lines)) // 2)
    for line in lines:
        _text_with_shadow(image, (MARGIN, y), line, font, CREAM, stroke)
        y += line_height

    _text_with_shadow(image, (MARGIN, 40), "SLEEP STORY", _font(54), AQUA, 5)

    pill_font = _font(52)
    text = f"{minutes} MIN"
    draw = ImageDraw.Draw(image)
    text_w = draw.textlength(text, font=pill_font)
    x0, y0 = MARGIN, HEIGHT - 112
    draw.rounded_rectangle((x0, y0, x0 + text_w + 64, y0 + 78), radius=39,
                           fill=PILL, outline=AQUA, width=3)
    draw.text((x0 + 32, y0 + 8), text, font=pill_font, fill=CREAM)

    out = work / "thumbnail.jpg"
    for quality in (92, 86, 80, 72):  # YouTube's limit is 2 MB
        image.save(out, "JPEG", quality=quality, optimize=True)
        if out.stat().st_size < 1_900_000:
            break
    return str(out)
