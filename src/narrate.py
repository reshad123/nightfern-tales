"""
Turns the story into one long narration file with edge-tts (free).

Each paragraph is spoken separately so we control the pauses: a short pause
between paragraphs and a longer one between scenes.
"""

import asyncio
from pathlib import Path

import edge_tts

from config import (
    PAUSE_PARAGRAPH_SECONDS,
    PAUSE_SCENE_SECONDS,
    TTS_RATE,
    TTS_VOICE,
    VOICE_CANDIDATES,
)
from src.media import duration_seconds, run

SAMPLE_TEXT = (
    "You step onto the platform, and the evening air is cool and soft. "
    "Somewhere ahead, a lamp glows warmly. There is nowhere you need to be, "
    "and nothing you need to do. You simply let your shoulders fall, and "
    "breathe out slowly."
)


async def _speak(text: str, path: Path, voice: str, rate: str, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
            if path.exists() and path.stat().st_size > 1000:
                return
            last = RuntimeError("edge-tts produced an empty file")
        except Exception as exc:  # network hiccups are common
            last = exc
        await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Text-to-speech failed for '{text[:40]}...': {last}")


async def _speak_all(jobs, voice: str, rate: str):
    for index, (text, path) in enumerate(jobs, 1):
        await _speak(text, path, voice, rate)
        if index % 10 == 0:
            print(f"  narrated {index}/{len(jobs)} paragraphs")


def _to_wav(src: Path, dst: Path):
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        what="convert narration to wav",
    )


def _silence(seconds: float, dst: Path):
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.2f}",
         "-c:a", "pcm_s16le", str(dst)],
        what="make silence",
    )


def narrate(story: dict, workdir: str):
    """Returns (path to narration.wav, duration in seconds)."""
    tts_dir = Path(workdir) / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    jobs, layout = [], []  # layout: ("para", index) or ("gap", kind)
    for s_index, paragraphs in enumerate(story["scenes"]):
        for p_index, text in enumerate(paragraphs):
            path = tts_dir / f"s{s_index:02d}_p{p_index:02d}.mp3"
            jobs.append((text, path))
            layout.append(("para", path))
            is_last_para = p_index == len(paragraphs) - 1
            is_last_scene = s_index == len(story["scenes"]) - 1
            if is_last_para and not is_last_scene:
                layout.append(("gap", "scene"))
            elif not is_last_para:
                layout.append(("gap", "para"))

    print(f"Narrating {len(jobs)} paragraphs with {TTS_VOICE} at rate {TTS_RATE}...")
    asyncio.run(_speak_all(jobs, TTS_VOICE, TTS_RATE))

    silence_para = tts_dir / "gap_para.wav"
    silence_scene = tts_dir / "gap_scene.wav"
    _silence(PAUSE_PARAGRAPH_SECONDS, silence_para)
    _silence(PAUSE_SCENE_SECONDS, silence_scene)

    list_lines = []
    for kind, item in layout:
        if kind == "para":
            wav = item.with_suffix(".wav")
            _to_wav(item, wav)
            list_lines.append(f"file '{wav.resolve().as_posix()}'")
        else:
            gap = silence_scene if item == "scene" else silence_para
            list_lines.append(f"file '{gap.resolve().as_posix()}'")

    list_path = tts_dir / "concat.txt"
    list_path.write_text("\n".join(list_lines) + "\n", encoding="utf-8")
    out = Path(workdir) / "narration.wav"
    run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_path), "-c", "copy", str(out)],
        what="join narration",
    )
    seconds = duration_seconds(str(out))
    print(f"Narration length: {seconds / 60:.1f} minutes")
    return str(out), seconds


def voice_test(workdir: str):
    """Make a short sample for each candidate voice so you can listen."""
    out_dir = Path(workdir) / "voice_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(SAMPLE_TEXT, out_dir / f"{voice}.mp3") for voice in VOICE_CANDIDATES]

    async def go():
        for (text, path), voice in zip(jobs, VOICE_CANDIDATES):
            await _speak(text, path, voice, TTS_RATE)
            print(f"  wrote {path}")

    asyncio.run(go())
    print(f"\nSamples are in {out_dir}. Listen, pick one, then set TTS_VOICE in config.py.")
