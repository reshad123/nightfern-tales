"""
Downloads calm landscape clips from Pexels (free API), preferring NIGHT footage.

Needs the PEXELS_API_KEY environment variable.

To find night clips without downloading everything, each search result's small
preview picture is measured first (average brightness); only the darkest clips
are downloaded. Anything still too bright gets darkened in the render step.
"""

import io
import os
from pathlib import Path

import requests
from PIL import Image

from config import CLIPS_MINIMUM, CLIPS_WANTED, MAX_PREVIEW_LUMA

SEARCH_URL = "https://api.pexels.com/videos/search"
PER_KEYWORD_CAP = 4  # keep a mix of scenes instead of 12 near-identical clips


def _best_file(video: dict):
    """Pick an mp4 close to full HD (never 4K, to keep downloads small)."""
    candidates = [
        f for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4"
        and 1280 <= (f.get("width") or 0) <= 2000
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


def preview_brightness(url: str) -> float:
    """Average brightness (0-255) of a clip's preview picture; 128 if unknown."""
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        image = Image.open(io.BytesIO(resp.content)).convert("L").resize((64, 36))
        pixels = list(image.getdata())
        return sum(pixels) / len(pixels)
    except Exception:
        return 128.0


def pick_darkest(candidates, wanted: int, max_luma: float = MAX_PREVIEW_LUMA,
                 minimum: int = CLIPS_MINIMUM, per_keyword: int = PER_KEYWORD_CAP):
    """Choose the darkest candidates, with a cap per search keyword for variety.

    Candidates brighter than max_luma are only used if there would otherwise be
    fewer than `minimum` clips. Each candidate is a dict with 'luma' and 'keyword'.
    """
    ranked = sorted(candidates, key=lambda c: c["luma"])
    dark_enough = [c for c in ranked if c["luma"] <= max_luma]
    pool = dark_enough if len(dark_enough) >= minimum else ranked

    chosen, per = [], {}
    for rounds_cap in (per_keyword, 10 ** 6):  # second pass relaxes the cap
        for c in pool:
            if len(chosen) >= wanted:
                break
            if c in chosen or per.get(c["keyword"], 0) >= rounds_cap:
                continue
            chosen.append(c)
            per[c["keyword"]] = per.get(c["keyword"], 0) + 1
    return chosen


def find_candidates(keywords, headers):
    seen, found = set(), []
    for keyword in keywords:
        try:
            resp = requests.get(
                SEARCH_URL,
                headers=headers,
                params={"query": keyword, "orientation": "landscape",
                        "size": "medium", "per_page": 10},
                timeout=30,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
        except (requests.RequestException, ValueError) as exc:
            print(f"Pexels search failed for '{keyword}': {exc}")
            continue
        for video in videos:
            vid = video.get("id")
            if vid in seen or (video.get("duration") or 0) < 8:
                continue
            chosen_file = _best_file(video)
            if not chosen_file:
                continue
            seen.add(vid)
            found.append({
                "id": vid,
                "keyword": keyword,
                "link": chosen_file["link"],
                "preview": video.get("image") or "",
                "luma": preview_brightness(video["image"]) if video.get("image") else 128.0,
            })
    return found


def fetch_clips(keywords, out_dir: str, wanted: int = CLIPS_WANTED):
    """Download the darkest `wanted` clips. Returns a list of file paths."""
    headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    candidates = find_candidates(keywords, headers)
    print(f"Found {len(candidates)} candidate clips; choosing the darkest.")
    chosen = pick_darkest(candidates, wanted)

    paths = []
    for c in chosen:
        dest = out / f"clip_{c['id']}.mp4"
        try:
            _download(c["link"], dest)
        except requests.RequestException as exc:
            print(f"Download failed for clip {c['id']}: {exc}")
            continue
        paths.append(str(dest))
        print(f"  got clip {len(paths)}/{len(chosen)} ({c['keyword']}, preview brightness {c['luma']:.0f})")

    if len(paths) < CLIPS_MINIMUM:
        raise RuntimeError(
            f"Only found {len(paths)} usable clips (need {CLIPS_MINIMUM}). "
            "Check PEXELS_API_KEY or the seed's keywords."
        )
    return paths
