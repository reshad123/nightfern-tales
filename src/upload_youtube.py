"""
Uploads a video to YouTube with the resumable protocol, in chunks.

Unlike a single big request, this never loads the whole file into memory and
can resume after a dropped connection, so it handles multi-gigabyte videos.
"""

import os
import time

import requests

from src.youtube_auth import get_access_token

INIT_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
    "?uploadType=resumable&part=snippet,status"
)
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
# Must be a multiple of 256 KiB. 16 MiB is a good size for CI runners.
CHUNK = 16 * 1024 * 1024
MAX_FAILURES = 8


def _trim_tags(tags, limit=450):
    """Keep valid, distinct tags within YouTube's total length limit."""
    kept, total = [], 0
    for tag in tags:
        tag = str(tag).strip()
        if not tag or len(tag) > 60 or tag in kept:
            continue
        if total + len(tag) + 1 > limit:
            continue
        kept.append(tag)
        total += len(tag) + 1
    return kept


def _init_session(token: str, metadata: dict, size: int) -> str:
    import json

    resp = requests.post(
        INIT_URL,
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": "video/mp4",
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"YouTube upload could not start ({resp.status_code}): {resp.text[:600]}"
        )
    location = resp.headers.get("Location")
    if not location:
        raise RuntimeError("YouTube did not return an upload session URL.")
    return location


def _offset_from(resp) -> int:
    """Next byte to send, from the Range header of a 308 response."""
    rng = resp.headers.get("Range")
    if not rng:
        return 0
    return int(rng.split("-")[-1]) + 1


def _ask_progress(session: str, token: str, size: int):
    """Ask YouTube how much it already has. Returns (offset, finished_json)."""
    resp = requests.put(
        session,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Length": "0",
            "Content-Range": f"bytes */{size}",
        },
        timeout=60,
        allow_redirects=False,
    )
    if resp.status_code in (200, 201):
        return size, resp.json()
    if resp.status_code == 308:
        return _offset_from(resp), None
    raise RuntimeError(f"Could not resume upload ({resp.status_code}): {resp.text[:300]}")


def upload_video(video_path, title, description, tags, privacy="private"):
    """Upload and return YouTube's video resource (it has the video 'id')."""
    size = os.path.getsize(video_path)
    if size == 0:
        raise RuntimeError("The video file is empty.")

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": _trim_tags(tags),
            "categoryId": "24",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }

    token = get_access_token()
    session = _init_session(token, metadata, size)
    print(f"Uploading {size / 1_000_000:.0f} MB as '{privacy}'...")

    offset, failures, last_pct = 0, 0, -1
    with open(video_path, "rb") as handle:
        while True:
            handle.seek(offset)
            chunk = handle.read(CHUNK)
            end = offset + len(chunk) - 1
            try:
                resp = requests.put(
                    session,
                    data=chunk,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {offset}-{end}/{size}",
                        "Content-Type": "video/mp4",
                    },
                    timeout=300,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                failures += 1
                if failures > MAX_FAILURES:
                    raise RuntimeError(f"Upload kept failing: {exc}") from exc
                print(f"  connection problem ({exc}); resuming...")
                time.sleep(min(60, 5 * failures))
                offset, done = _ask_progress(session, token, size)
                if done:
                    return done
                continue

            if resp.status_code in (200, 201):
                print("Upload complete.")
                return resp.json()

            if resp.status_code == 308:
                offset = _offset_from(resp)
                failures = 0
                pct = int(offset * 100 / size)
                if pct != last_pct and pct % 10 == 0:
                    print(f"  {pct}%")
                    last_pct = pct
                continue

            failures += 1
            if failures > MAX_FAILURES:
                raise RuntimeError(
                    f"Upload failed ({resp.status_code}): {resp.text[:500]}"
                )
            if resp.status_code == 401:
                token = get_access_token()
            elif resp.status_code not in (500, 502, 503, 504):
                raise RuntimeError(
                    f"Upload failed ({resp.status_code}): {resp.text[:500]}"
                )
            print(f"  server said {resp.status_code}; resuming...")
            time.sleep(min(60, 5 * failures))
            offset, done = _ask_progress(session, token, size)
            if done:
                return done


def set_thumbnail(video_id: str, image_path: str) -> bool:
    """Attach a custom thumbnail. Returns False (with the reason) if refused."""
    with open(image_path, "rb") as handle:
        data = handle.read()
    resp = requests.post(
        THUMB_URL,
        params={"videoId": video_id, "uploadType": "media"},
        data=data,
        headers={
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "image/jpeg",
        },
        timeout=120,
    )
    if resp.status_code == 200:
        print("Custom thumbnail set.")
        return True
    print(
        f"Thumbnail was not set ({resp.status_code}): {resp.text[:300]}\n"
        "If this says the channel is not allowed to use custom thumbnails, "
        "verify the channel by phone at youtube.com/verify, then upload "
        "thumbnail.jpg by hand in YouTube Studio."
    )
    return False
