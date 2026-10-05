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

import math
from pathlib import Path

from config import VIDEO_CRF, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from src.media import run

FPS = VIDEO_FPS
LOOP_SECONDS = {"snow": 60, "rain": 60, "stars": 12, "mist": 120}
OPACITY = {"snow": 0.55, "rain": 0.42, "stars": 0.90, "mist": 0.16}
KINDS = tuple(LOOP_SECONDS)


def _frames(kind: str) -> int:
    return LOOP_SECONDS[kind] * FPS


def _dots(w: int, h: int, density: float, blur: str) -> str:
    """One frozen random field of dots, softened. density = dots per 1000 pixels."""
    return (
        f"nullsrc=s={w}x{h}:r={FPS},format=gray,"
        f"geq=lum='if(lt(random(1)*1000,{density}),255,0)',"
        f"trim=end_frame=1,{blur}"
    )


def graph(kind: str) -> str:
    """ffmpeg filter graph that ends in a labelled stream [fx] (640x360)."""
    if kind not in LOOP_SECONDS:
        raise ValueError(f"Unknown overlay '{kind}'. Choose from: {', '.join(KINDS)}")
    n = _frames(kind)
    phase = "mod(abs(sin(X*12.9898+Y*78.233)*43758.5453),1)"
    if kind == "snow":
        near = _dots(640, 360, 2.4, "gblur=sigma=0.5") + \
            f",loop=-1:1:0,scroll=v={5 / n:.7f}:h={1 / n:.7f}"
        big = _dots(160, 90, 1.5, "gblur=sigma=0.55") + \
            f",scale=640:360:flags=bilinear,loop=-1:1:0,scroll=v={10 / n:.7f}:h={-1 / n:.7f}"
        return f"{near}[a];{big}[b];[a][b]blend=all_mode=lighten,format=yuv420p[fx]"
    if kind == "rain":
        fine = _dots(640, 360, 3.4, "gblur=sigma=0.35:sigmaV=9") + \
            f",loop=-1:1:0,scroll=v={54 / n:.7f}:h={-5 / n:.7f}"
        near = _dots(320, 180, 1.8, "gblur=sigma=0.35:sigmaV=7") + \
            f",scale=640:360:flags=bilinear,loop=-1:1:0,scroll=v={78 / n:.7f}:h={-5 / n:.7f}"
        return f"{fine}[a];{near}[b];[a][b]blend=all_mode=lighten,format=yuv420p[fx]"
    if kind == "stars":
        omega = 2 * math.pi * 2 / LOOP_SECONDS["stars"]
        return (
            _dots(640, 360, 1.4, "gblur=sigma=0.5")
            + ",loop=-1:1:0,"
            f"geq=lum='p(X,Y)*(0.55+0.45*sin(T*{omega:.5f}+6.2832*{phase}))"
            "*clip(1.5-Y/H*1.8,0,1)',format=yuv420p[fx]"
        )
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
