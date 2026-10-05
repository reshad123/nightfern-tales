"""
Builds the final video with ffmpeg only (no MoviePy, so it is fast and light).

Plan:
  1. Each Pexels clip is scaled to 1080p, dimmed slightly, and given soft
     fade-in / fade-out, then encoded once.
  2. The clips are joined into one "base" video (a few minutes long).
  3. The base video is repeated to match the narration length without
     re-encoding (stream copy), which takes seconds instead of an hour.
  4. The narration is mixed with a soft rain-like noise bed and faded in/out.
"""

import re
from pathlib import Path

from config import (
    BED_VOLUME,
    CLIP_MAX_SECONDS,
    END_TAIL_SECONDS,
    NIGHT_MIN_FACTOR,
    NIGHT_TARGET_LUMA,
    NIGHT_TINT_BLUE,
    NIGHT_TINT_WARM,
    VIDEO_CRF,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from src.media import duration_seconds, run


def clip_luma(path: str) -> float:
    """Average brightness of a clip (video-range luma, 16-235), from 3 sampled frames."""
    middle = max(0.0, duration_seconds(path) / 2)
    proc = run(
        ["ffmpeg", "-v", "error", "-ss", f"{middle:.2f}", "-i", path,
         "-frames:v", "3", "-vf", "signalstats,metadata=print:file=-",
         "-f", "null", "-"],
        what="measure clip brightness",
    )
    values = [float(v) for v in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", proc.stdout)]
    return sum(values) / len(values) if values else 100.0


def night_factor(luma: float) -> float:
    """How much to scale a clip's brightness so it ends near the night target."""
    return max(NIGHT_MIN_FACTOR, min(1.0, NIGHT_TARGET_LUMA / max(luma, 1.0)))


def _night_filters(factor: float) -> str:
    """Night look in ONE cheap lookup pass: darken the brightness (relative to video black,
    16), nudge colour towards moonlight blue, and desaturate slightly; then a soft vignette.
    (An earlier version used `colorbalance`, which was 15x slower at 1080p.)"""
    return (
        f"lutyuv=y='16+(val-16)*{factor:.3f}':"
        f"u='128+(val-128)*0.9+{NIGHT_TINT_BLUE}':"
        f"v='128+(val-128)*0.9-{NIGHT_TINT_WARM}',"
        "vignette=angle=PI/5"
    )


def _normalize_clip(src: str, dst: Path, intermediate: bool) -> float:
    seconds = min(duration_seconds(src), float(CLIP_MAX_SECONDS))
    fade = min(1.5, seconds / 4)
    luma = clip_luma(src)
    factor = night_factor(luma)
    vf = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,fps={VIDEO_FPS},"
        f"{_night_filters(factor)},"
        f"fade=t=in:st=0:d={fade:.2f},"
        f"fade=t=out:st={seconds - fade:.2f}:d={fade:.2f},"
        "format=yuv420p"
    )
    if intermediate:  # an overlay pass follows and does the final encode
        codec = ["-preset", "ultrafast", "-crf", "18"]
    else:
        codec = ["-preset", "veryfast", "-crf", str(VIDEO_CRF),
                 "-maxrate", "3000k", "-bufsize", "6000k"]
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-t", f"{seconds:.2f}", "-i", src,
         "-vf", vf, "-an", "-c:v", "libx264", *codec,
         "-g", str(2 * VIDEO_FPS), "-keyint_min", str(2 * VIDEO_FPS),
         "-sc_threshold", "0", str(dst)],
        what=f"encode clip {Path(src).name}",
    )
    print(f"    brightness {luma:.0f} -> darkened x{factor:.2f}")
    return seconds


def build_base(clip_paths, workdir: str, intermediate: bool = False):
    """Join the night-graded clips into base.mp4. Returns (path, seconds)."""
    work = Path(workdir) / "segments"
    work.mkdir(parents=True, exist_ok=True)
    lines, total = [], 0.0
    for i, src in enumerate(clip_paths, 1):
        dst = work / f"seg_{i:02d}.mp4"
        total += _normalize_clip(src, dst, intermediate)
        lines.append(f"file '{dst.resolve().as_posix()}'")
        print(f"  encoded clip {i}/{len(clip_paths)}")
    list_path = work / "concat.txt"
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    base = Path(workdir) / "base.mp4"
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_path), "-c", "copy", str(base)],
        what="join clips",
    )
    print(f"Base video: {total / 60:.1f} minutes")
    return str(base), total


def build_audio(narration_wav: str, workdir: str):
    """Mix narration with the noise bed. Returns (path, total seconds)."""
    narration_seconds = duration_seconds(narration_wav)
    total = narration_seconds + END_TAIL_SECONDS
    fade_out = min(25.0, total / 4)
    graph = (
        f"[0:a]loudnorm=I=-21:TP=-2:LRA=7,aresample=44100,"
        f"apad=pad_dur={END_TAIL_SECONDS}[voice];"
        f"[1:a]highpass=f=250,lowpass=f=3200,volume={BED_VOLUME}[bed];"
        "[voice][bed]amix=inputs=2:duration=first:normalize=0,"
        "afade=t=in:st=0:d=3,"
        f"afade=t=out:st={total - fade_out:.2f}:d={fade_out:.2f},"
        "alimiter=limit=0.95[a]"
    )
    out = Path(workdir) / "mix.m4a"
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", narration_wav,
         "-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.3:sample_rate=44100",
         "-filter_complex", graph, "-map", "[a]", "-t", f"{total:.2f}",
         "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "2", str(out)],
        what="mix audio",
    )
    return str(out), total


def build_final(base: str, mix: str, total: float, workdir: str) -> str:
    """Repeat the base video to the audio length and add the audio."""
    out = Path(workdir) / "final.mp4"
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", base,
         "-i", mix, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "copy", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)],
        what="build final video",
    )
    print(f"Final video: {total / 60:.1f} minutes, "
          f"{out.stat().st_size / 1_000_000:.0f} MB")
    return str(out)


def build_preview(final: str, workdir: str, seconds: int = 180) -> str:
    """A short cut from the start so you can check the look and sound fast."""
    out = Path(workdir) / "preview_first_3_minutes.mp4"
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", final, "-t", str(seconds),
         "-c", "copy", "-movflags", "+faststart", str(out)],
        what="build preview",
    )
    return str(out)
