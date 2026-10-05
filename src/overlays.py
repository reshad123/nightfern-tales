"""
Soft night overlays made with ffmpeg only: snow, rain, stars and mist.

How it works
------------
Each effect is rendered ONCE as a short loop at 640x360 (a few seconds of work).
Every movement in a loop covers a whole number of screen heights/widths, and every
twinkle completes a whole number of cycles, so the loop repeats with no visible seam.
`apply_overlay` then screen-blends the loop onto the base video in a single pass,
which only ever ADDS light: the video's own colours are untouched.

Notes from testing (so nobody has to rediscover them)
- ffmpeg's `blend` filter: for the brightness plane, opacity mixes between the
  first input and the blended result. For the two colour planes the default mode is
  "normal", where opacity 0 returns the SECOND input, so they are set to opacity 1
  to keep the video's own colour.
- The effect layer's black must be 0, not 16 (video-range black), or it lifts the
  video's blacks into a haze: hence the `max(val-16,0)` lookup.
- Per-pixel `geq` work is done on tiny frames and only while building the loop.
"""

import io
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageChops

from config import VIDEO_CRF, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from src.media import duration_seconds, run

FPS = VIDEO_FPS
LOOP_SECONDS = {"snow": 60, "rain": 60, "stars": 6, "mist": 120}
OPACITY = {"snow": 0.60, "rain": 0.60, "stars": 1.00, "mist": 0.16}
KINDS = tuple(LOOP_SECONDS)


def _frames(kind: str) -> int:
    return LOOP_SECONDS[kind] * FPS


def _hash(seed: int) -> str:
    """Per-pixel pseudo-random number in [0, 1). ffmpeg's own random() produces RUNS of
    adjacent dots (one 'star' turned out to be a cluster of eight), so a hash is used."""
    return f"mod(abs(sin(X*12.9898+Y*78.233+{seed * 37.719})*43758.5453),1)"


def _dots(w: int, h: int, density: float, blur: str, seed: int = 1) -> str:
    """One frozen random field of isolated dots, softened. density = dots per 1000 pixels."""
    return (
        f"nullsrc=s={w}x{h}:r={FPS},format=gray,"
        f"geq=lum='if(lt({_hash(seed)}*1000,{density}),255,0)',"
        f"trim=end_frame=1,{blur}"
    )


def _bright_dots(w: int, h: int, density: float, blur: str, gain: float,
                 hq: bool = False, seed: int = 1) -> str:
    """Dots, blurred, then brightened. Blurring spreads a dot's light thin (a streak blurred
    9 px tall keeps only ~1/20 of its brightness), so the gain puts it back. This is cheap:
    it runs on the single frozen frame, before the loop.
    hq=True blurs in 16-bit: in 8-bit a wide, faint blur has only a handful of brightness
    levels, which turns a soft glow into a flat disc with a hard edge.
    Pick `gain` so a single dot peaks near 200 (not above 255), or the core flattens."""
    if not hq:
        return _dots(w, h, density, blur, seed) + f",lut=y='min(255,val*{gain})'"
    margin = 16  # keep big glows off the border, where the blur reflects and doubles them
    inside = f"gt(X,{margin})*lt(X,W-{margin})*gt(Y,{margin})*lt(Y,H-{margin})"
    return (
        f"nullsrc=s={w}x{h}:r={FPS},format=gray,"
        f"geq=lum='if(lt({_hash(seed)}*1000,{density})*{inside},255,0)',"
        f"trim=end_frame=1,format=gray16le,{blur},"
        f"lut=y='min(65535,val*{gain})',format=gray"
    )


def _star_layer(density: float, sigma: float, gain: float, twinkle_floor: float,
                omega: float, cell: int, seed: int) -> str:
    """One size of star, drawn at the loop's own 640x360 size so it stays smooth and round.
    Tiny stars (cell=1) twinkle with a per-pixel random phase. Bigger stars use a phase
    that changes only slowly across the frame, so every part of one star shares (almost)
    the same phase: a grid of phases cut stars in half along the grid lines."""
    if cell == 1:
        phase = "mod(abs(sin(X*12.9898+Y*78.233)*43758.5453),1)"
    else:
        phase = ("mod(X*0.0021+Y*0.0034+0.35*sin(X*0.0090+1)+0.35*sin(Y*0.0110+2),1)")
    amp = 1 - twinkle_floor
    return (
        _bright_dots(640, 360, density, f"gblur=sigma={sigma}:steps=6", gain,
                     hq=sigma >= 1.0, seed=seed)
        + ",loop=-1:1:0,"
        f"geq=lum='p(X,Y)*({twinkle_floor}+{amp}*sin(T*{omega:.5f}+6.2832*{phase}))"
        "*clip(1.6-Y/H*1.7,0,1)'"
    )


def graph(kind: str) -> str:
    """ffmpeg filter graph that ends in a labelled stream [fx] (640x360)."""
    if kind not in LOOP_SECONDS:
        raise ValueError(f"Unknown overlay '{kind}'. Choose from: {', '.join(KINDS)}")
    n = _frames(kind)
    phase = "mod(abs(sin(X*12.9898+Y*78.233)*43758.5453),1)"
    if kind == "snow":
        near = _dots(640, 360, 2.4, "gblur=sigma=0.5", seed=1) + \
            f",loop=-1:1:0,scroll=v={5 / n:.7f}:h={1 / n:.7f}"
        big = _dots(160, 90, 1.5, "gblur=sigma=0.55", seed=2) + \
            f",scale=640:360:flags=bilinear,loop=-1:1:0,scroll=v={10 / n:.7f}:h={-1 / n:.7f}"
        return f"{near}[a];{big}[b];[a][b]blend=all_mode=lighten,format=yuv420p[fx]"
    if kind == "rain":
        fine = _bright_dots(640, 360, 1.0, "gblur=sigma=0.4:sigmaV=7", 8, seed=3) + \
            f",loop=-1:1:0,scroll=v={54 / n:.7f}:h={-5 / n:.7f}"
        near = _bright_dots(320, 180, 0.30, "gblur=sigma=0.5:sigmaV=5", 10, seed=4) + \
            f",scale=640:360:flags=bicubic,loop=-1:1:0,scroll=v={78 / n:.7f}:h={-5 / n:.7f}"
        return f"{fine}[a];{near}[b];[a][b]blend=all_mode=lighten,format=yuv420p[fx]"
    if kind == "stars":
        omega = 2 * math.pi / LOOP_SECONDS["stars"]  # one calm twinkle per loop
        small = _star_layer(2.6, 0.5, 1.4, 0.45, omega, cell=1, seed=5)
        medium = _star_layer(0.12, 1.6, 10, 0.35, omega, cell=14, seed=6)
        large = _star_layer(0.02, 3.0, 40, 0.30, omega, cell=30, seed=7)
        return (f"{small}[a];{medium}[b];{large}[c];[a][b]blend=all_mode=lighten[ab];"
                "[ab][c]blend=all_mode=lighten,format=yuv420p[fx]")
    if kind == "mist":
        return (
            f"nullsrc=s=24x14:r={FPS},format=gray,geq=lum='random(1)*255',"
            "trim=end_frame=1,gblur=sigma=1.4,scale=640:360:flags=bicubic,"
            "geq=lum='p(X,Y)*clip(Y/H*1.5-0.35,0,1)',"
            f"loop=-1:1:0,scroll=h={1 / n:.7f},format=yuv420p[fx]"
        )
    raise ValueError(f"Unknown overlay '{kind}'. Choose from: {', '.join(KINDS)}")


def make_loop(kind: str, workdir: str) -> str:
    out = Path(workdir) / f"fx_{kind}.mp4"
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", graph(kind),
         "-map", "[fx]", "-t", str(LOOP_SECONDS[kind]), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
         "-pix_fmt", "yuv420p", str(out)],
        what=f"build {kind} overlay",
    )
    return str(out)


def apply_overlay(base: str, kind: str, workdir: str) -> str:
    """Blend the effect onto `base` and re-encode once. Returns the new file."""
    loop = make_loop(kind, workdir)
    out = Path(workdir) / "base_fx.mp4"
    fc = (
        "[1:v]lutyuv=y='max(val-16,0)',"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:flags=bilinear[l];"
        f"[0:v][l]blend=c0_mode=screen:c0_opacity={OPACITY[kind]}:"
        "c1_mode=normal:c1_opacity=1:c2_mode=normal:c2_opacity=1:shortest=1[v]"
    )
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", base, "-stream_loop", "-1",
         "-i", loop, "-filter_complex", fc, "-map", "[v]",
         "-c:v", "libx264", "-preset", "superfast", "-crf", str(VIDEO_CRF),
         "-maxrate", "3000k", "-bufsize", "6000k", "-g", str(2 * FPS),
         "-keyint_min", str(2 * FPS), "-sc_threshold", "0",
         "-pix_fmt", "yuv420p", str(out)],
        what=f"apply {kind} overlay",
    )
    return str(out)


# Share of the picture (%) that should be visibly brightened, measured on the finished video.
# Below the low end the effect is too faint to notice; far above the high end it is too busy.
EXPECTED_VISIBILITY = {"snow": (0.4, 4.0), "rain": (0.8, 8.0), "stars": (0.4, 4.0), "mist": (5.0, 45.0)}


def _gray_frame(path: str, seconds: float) -> Image.Image:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{seconds:.2f}", "-i", path, "-frames:v", "1",
         "-vf", "format=gray", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True,
    )
    return Image.open(io.BytesIO(proc.stdout)).convert("L")


def overlay_visibility(before: str, after: str) -> float:
    """Average share (%) of pixels the overlay brightens by 14+ levels (out of 255),
    measured on three frames of the finished video."""
    total = duration_seconds(after)
    shares = []
    for fraction in (0.25, 0.5, 0.75):
        a, b = _gray_frame(before, total * fraction), _gray_frame(after, total * fraction)
        added = ImageChops.subtract(b, a)  # brightness added by the overlay (never negative)
        bright = sum(added.histogram()[14:])
        shares.append(100.0 * bright / (a.width * a.height))
    return sum(shares) / len(shares)


def overlay_report(before: str, after: str, kind: str) -> str:
    share = overlay_visibility(before, after)
    low, high = EXPECTED_VISIBILITY[kind]
    if share < low:
        verdict = "WARNING: too faint to notice. Raise OPACITY in src/overlays.py."
    elif share > high:
        verdict = "WARNING: very busy. Lower OPACITY in src/overlays.py."
    else:
        verdict = "looks right."
    return f"Overlay check: {kind} visibly brightens {share:.2f}% of the picture ({verdict})"
