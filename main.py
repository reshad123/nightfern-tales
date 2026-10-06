"""
Nightfern Tales: makes one sleep-story video.

    python main.py              # full run; uploads only if UPLOAD=true
    python main.py story-only   # write just the story text (cheap quality check)
    python main.py voice-test   # short samples of each candidate voice

Environment variables: GROQ_API_KEY, PEXELS_API_KEY, and for uploads
YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. Optional: UPLOAD,
STORY_SEED, PRIVACY_STATUS, TTS_VOICE, BED_VOLUME.
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import (
    BASE_TAGS,
    DISCLAIMER,
    HASHTAGS,
    MIN_LEAD_MINUTES,
    OVERLAYS_ENABLED,
    PRIVACY_STATUS,
    PUBLISH_TIME,
    PUBLISH_TZ,
    SAFETY_LINE,
    WORKDIR,
)
from src.narrate import narrate, voice_test
from src.overlays import apply_overlay, overlay_report
from src.render import build_audio, build_base, build_final, build_preview
from src.schedule import describe_slot, next_publish_slot, to_youtube_time
from src.story import (
    generate_story,
    load_used,
    pick_seed,
    record_used,
    story_to_text,
)
from src.thumbnail import make_thumbnail
from src.upload_youtube import set_thumbnail, upload_video
from src.visuals import fetch_clips
from src.youtube_auth import require_expected_channel

WORDS_PER_MINUTE = 125  # rough speaking speed at the slowed pace


def fresh_workdir() -> Path:
    work = Path(WORKDIR)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    return work


def build_metadata(story: dict, seed: dict, total_seconds: float) -> dict:
    minutes = max(5, int(round(total_seconds / 60 / 5.0)) * 5)
    suffix = f" ({minutes} Minutes)"
    prefix = "Sleep Story: "
    room = 100 - len(prefix) - len(suffix)
    title = f"{prefix}{story['title'][:room].rstrip()}{suffix}"
    description = "\n\n".join(
        [
            f"{story['title']}: a calm sleep story for adults.",
            story["summary"],
            DISCLAIMER,
            "Tip: dim your screen, turn the volume low, and let the story play.\n"
            + SAFETY_LINE,
            HASHTAGS,
        ]
    )
    tags = BASE_TAGS + [seed["idea"].lower()]
    return {"title": title, "description": description, "tags": tags,
            "minutes": minutes, "seed_id": seed["id"]}


def command_story_only():
    seed = pick_seed()
    print(f"Story seed: {seed['id']}")
    work = fresh_workdir()
    story = generate_story(seed)
    (work / "story.txt").write_text(story_to_text(story), encoding="utf-8")
    est = story["words"] / WORDS_PER_MINUTE
    print(f"\nWrote {work / 'story.txt'}: {story['words']} words, about {est:.0f} minutes narrated.")


def command_run(upload: bool):
    seed = pick_seed()
    print(f"Story seed: {seed['id']} (upload={'yes' if upload else 'no, dry run'})")
    work = fresh_workdir()

    if upload:
        require_expected_channel()  # fail fast, before spending any effort

    story = generate_story(seed)
    (work / "story.txt").write_text(story_to_text(story), encoding="utf-8")

    narration, _ = narrate(story, str(work))

    print("Fetching footage...")
    clips = fetch_clips(seed["keywords"], str(work / "clips"))

    print("Rendering...")
    overlay = seed.get("overlay") if OVERLAYS_ENABLED else None
    base, _ = build_base(clips, str(work), intermediate=bool(overlay))
    if overlay:
        print(f"Adding {overlay} overlay...")
        plain = base
        base = apply_overlay(base, overlay, str(work))
        try:
            print(overlay_report(plain, base, overlay))
        except Exception as exc:  # a measuring problem must never stop the video
            print(f"(could not measure the overlay: {exc})")
    mix, total = build_audio(narration, str(work))
    final = build_final(base, mix, total, str(work))
    build_preview(final, str(work))

    meta = build_metadata(story, seed, total)
    meta["privacy"] = PRIVACY_STATUS
    (work / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    thumbnail = None
    try:
        thumbnail = make_thumbnail(base, story["title"], meta["minutes"], str(work), seed["id"])
    except Exception as exc:  # a thumbnail problem must never stop the upload
        print(f"Could not make a thumbnail: {exc}")

    if not upload:
        print(
            "\nDry run finished. Nothing was uploaded. Review workdir/story.txt, "
            "mix.m4a (the FULL audio) and preview_first_3_minutes.mp4 (only the first 3 minutes; "
            "the full video is built but too large to attach)."
        )
        return

    quick = os.environ.get("QUICK_TEST", "").strip().lower() in ("1", "true", "yes")
    visibility, publish_at = PRIVACY_STATUS, None
    if quick:
        visibility = "private"  # a short test video must never go public by accident
    elif PRIVACY_STATUS == "public":
        slot = next_publish_slot(datetime.now(timezone.utc), load_used(),
                                 PUBLISH_TIME, PUBLISH_TZ, MIN_LEAD_MINUTES)
        publish_at, visibility = to_youtube_time(slot), "private"
        print(f"Scheduled: it stays private now and YouTube makes it public at "
              f"{describe_slot(slot, PUBLISH_TZ)}")

    result = upload_video(
        final, meta["title"], meta["description"], meta["tags"], visibility, publish_at
    )
    if not quick:
        record_used(seed["id"], story["title"], publish_at)
    if thumbnail and result.get("id"):
        try:
            set_thumbnail(result["id"], thumbnail)
        except Exception as exc:
            print(f"Thumbnail was not set: {exc}")
    state = f"public at {publish_at}" if publish_at else visibility
    print(f"Done: https://www.youtube.com/watch?v={result.get('id')} ({state})")


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "voice-test":
        voice_test(WORKDIR)
    elif command == "story-only":
        command_story_only()
    elif command == "run":
        upload = os.environ.get("UPLOAD", "false").strip().lower() in ("1", "true", "yes")
        command_run(upload)
    else:
        raise SystemExit("Usage: python main.py [run|story-only|voice-test]")


if __name__ == "__main__":
    main()
