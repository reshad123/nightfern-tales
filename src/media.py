"""Small helpers for running ffmpeg / ffprobe."""

import subprocess


def run(cmd, what="command"):
    """Run a command, raising a readable error (with ffmpeg's last lines)."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-25:])
        raise RuntimeError(f"{what} failed (exit {proc.returncode}):\n{tail}")
    return proc


def duration_seconds(path: str) -> float:
    """Length of an audio/video file in seconds, via ffprobe."""
    proc = run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        what="ffprobe",
    )
    return float(proc.stdout.strip())
