"""
Downloads calm landscape clips from Pexels (free API).

Needs the PEXELS_API_KEY environment variable.
"""

import os
from pathlib import Path

import requests

from config import CLIPS_MINIMUM, CLIPS_WANTED

SEARCH_URL = "https://api.pexels.com/videos/search"


def _best_file(video: dict):
    """Pick an mp4 close to full HD (never 4K, to keep downloads small)."""
    candidates = [
        f for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4"
        and (f.get("width") or 0) >= 1280
        and (f.get("width") or 0) <= 2000
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda f: abs((f.get("width") or 0) - 1920))


def _download(url: str, dest: Path):
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as out:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                out.write(chunk)


def fetch_clips(keywords, out_dir: str, wanted: int = CLIPS_WANTED):
    """Download up to `wanted` distinct clips. Returns a list of file paths."""
    api_key = os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": api_key}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    seen, paths = set(), []
    # Several rounds over the keywords so each one contributes a few clips.
    for page in (1, 2):
        for keyword in keywords:
            if len(paths) >= wanted:
                break
            try:
                resp = requests.get(
                    SEARCH_URL,
                    headers=headers,
                    params={
                        "query": keyword,
                        "orientation": "landscape",
                        "size": "medium",
                        "per_page": 6,
                        "page": page,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                videos = resp.json().get("videos", [])
            except (requests.RequestException, ValueError) as exc:
                print(f"Pexels search failed for '{keyword}': {exc}")
                continue

            taken_for_keyword = 0
            for video in videos:
                if len(paths) >= wanted or taken_for_keyword >= 2:
                    break
                vid = video.get("id")
                if vid in seen or (video.get("duration") or 0) < 8:
                    continue
                chosen = _best_file(video)
                if not chosen:
                    continue
                dest = out / f"clip_{vid}.mp4"
                try:
                    _download(chosen["link"], dest)
                except requests.RequestException as exc:
                    print(f"Download failed for clip {vid}: {exc}")
                    continue
                seen.add(vid)
                paths.append(str(dest))
                taken_for_keyword += 1
                print(f"  got clip {len(paths)}/{wanted} ({keyword})")

    if len(paths) < CLIPS_MINIMUM:
        raise RuntimeError(
            f"Only found {len(paths)} usable clips (need {CLIPS_MINIMUM}). "
            "Check PEXELS_API_KEY or the seed's keywords."
        )
    return paths
