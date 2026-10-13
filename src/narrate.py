"""
Turns the story into one long narration file. Free, no accounts.

Engine 1 (default): Kokoro, an open-source voice that runs on the GitHub runner itself.
Engine 2 (backup):  edge-tts (Microsoft's online voices), used only if Kokoro fails.

Each paragraph is spoken separately so we control the pauses: a short pause
between paragraphs and a longer one between scenes.

Settings (environment variables, all optional):
  TTS_ENGINE      kokoro (default) or edge
  KOKORO_VOICE    default af_heart. Others: af_bella, af_nicole, am_michael, am_fenrir, bf_emma, bm_george
  KOKORO_SPEED    default 0.8 (1.0 = normal speech; lower = slower, calmer)
"""

import asyncio
import os
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


TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro").strip().lower()
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "af_heart").strip() or "af_heart"
KOKORO_SPEED = float(os.environ.get("KOKORO_SPEED", "0.8") or 0.8)
KOKORO_RATE = 24000
KOKORO_CANDIDATES = ["af_heart", "af_bella", "af_nicole", "am_michael", "am_fenrir", "bf_emma", "bm_george"]


def _kokoro_pipeline(voice: str):
    from kokoro import KPipeline

    return KPipeline(lang_code="b" if voice.startswith("b") else "a")


def _kokoro_say(pipeline, text: str, voice: str, speed: float, wav_path: Path):
    """Speak one paragraph and write it as a 24 kHz mono wav."""
    import numpy as np
    import soundfile as sf

    pieces = []
    for result in pipeline(text, voice=voice, speed=speed):
        audio = result.audio
        if audio is None:
            continue
        arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        pieces.append(arr.astype("float32").reshape(-1))
    if not pieces:
        raise RuntimeError(f"Kokoro returned no audio for '{text[:40]}...'")
    samples = np.concatenate(pieces)
    if len(samples) < KOKORO_RATE * 0.3:
        raise RuntimeError(f"Kokoro audio too short for '{text[:40]}...'")
    sf.write(str(wav_path), samples, KOKORO_RATE)


def _kokoro_speak_all(jobs, voice: str, speed: float):
    pipeline = _kokoro_pipeline(voice)
    for index, (text, path) in enumerate(jobs, 1):
        _kokoro_say(pipeline, text, voice, speed, path.with_suffix(".wav"))
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

    used_kokoro = False
    if TTS_ENGINE != "edge":
        try:
            print(f"Narrating {len(jobs)} paragraphs with Kokoro voice {KOKORO_VOICE} at speed {KOKORO_SPEED}...")
            _kokoro_speak_all(jobs, KOKORO_VOICE, KOKORO_SPEED)
            used_kokoro = True
        except Exception as exc:
            print(f"Kokoro failed ({type(exc).__name__}: {str(exc)[:200]}). Trying edge-tts instead...")
            for leftover in tts_dir.glob("s*_p*.wav"):  # never mix two voices in one story
                leftover.unlink()
    if not used_kokoro:
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
            if not used_kokoro:
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

    if TTS_ENGINE != "edge":
        for voice in KOKORO_CANDIDATES:
            pipeline = _kokoro_pipeline(voice)
            path = out_dir / f"kokoro_{voice}.wav"
            _kokoro_say(pipeline, SAMPLE_TEXT, voice, KOKORO_SPEED, path)
            print(f"  wrote {path}")
        print(f"\nSamples are in {out_dir}. Listen, pick one, then set KOKORO_VOICE (repo variable or env).")
        return

    jobs = [(SAMPLE_TEXT, out_dir / f"{voice}.mp3") for voice in VOICE_CANDIDATES]

    async def go():
        for (text, path), voice in zip(jobs, VOICE_CANDIDATES):
            await _speak(text, path, voice, TTS_RATE)
            print(f"  wrote {path}")

    asyncio.run(go())
    print(f"\nSamples are in {out_dir}. Listen, pick one, then set TTS_VOICE in config.py.")
