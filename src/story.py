"""
Writes a sleep story with Groq's free tier.

Two steps keep the quality up and the token usage low:
  1. one call writes a short outline (title, summary, 8 scene beats);
  2. one call per scene writes the actual text, given the outline and the end
     of the previous scene, so the story stays consistent and keeps winding
     down towards the end.

Needs the GROQ_API_KEY environment variable.
"""

import json
import os
import re
import time

import requests

from config import (
    GROQ_MODEL_ORDER,
    GROQ_PAUSE_SECONDS,
    SCENE_TARGET_WORDS,
    SEEDS,
    USED_STORIES_PATH,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Words that do not belong in a sleep story. A scene containing any of these
# is rewritten.
BANNED_RE = re.compile(
    r"\b(scream\w*|blood\w*|dead|death|dies|die|died|dying|kill\w*|murder\w*|"
    r"terrif\w*|terror\w*|panic\w*|danger\w*|scary|afraid|ghost\w*|monster\w*|"
    r"weapon\w*|guns?|emergency|hospital\w*|funeral\w*|grief|tragic\w*|"
    r"tragedy|crash\w*|fear\w*|horror)\b",
    re.IGNORECASE,
)

_use_reasoning_effort = True


class GroqError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Groq call with retries
# --------------------------------------------------------------------------
def _retry_after(resp) -> float:
    try:
        wait = float(resp.headers.get("retry-after", ""))
    except ValueError:
        wait = 30.0
    return min(max(wait, 5.0), 90.0) + 2.0


def call_groq(messages, max_tokens=2600, attempts=7) -> str:
    """Send a chat request, rotating models and waiting out rate limits."""
    global _use_reasoning_effort
    api_key = os.environ["GROQ_API_KEY"]
    last = "no attempt was made"
    for i in range(attempts):
        model = GROQ_MODEL_ORDER[i % len(GROQ_MODEL_ORDER)]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "max_completion_tokens": max_tokens,
        }
        if _use_reasoning_effort:
            payload["reasoning_effort"] = "low"
        try:
            resp = requests.post(
                GROQ_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=120,
            )
        except requests.RequestException as exc:
            last = f"network error: {exc}"
            print(last)
            time.sleep(10)
            continue

        if resp.status_code == 200:
            try:
                content = resp.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, ValueError):
                last = f"{model}: unexpected response shape"
                print(last)
                continue
            if content.strip():
                return content.strip()
            last = f"{model}: empty reply"
            print(last)
            continue

        last = f"{model}: HTTP {resp.status_code} {resp.text[:300]}"
        print(last)
        if resp.status_code in (401, 403):
            raise GroqError(f"Groq rejected the API key: {last}")
        if resp.status_code == 400 and "reasoning_effort" in resp.text:
            _use_reasoning_effort = False
        elif resp.status_code == 429:
            time.sleep(_retry_after(resp))
        elif resp.status_code >= 500:
            time.sleep(10)
    raise GroqError(f"Groq failed after {attempts} attempts. Last problem: {last}")


# --------------------------------------------------------------------------
# Text cleaning helpers
# --------------------------------------------------------------------------
def count_words(text: str) -> int:
    return len(text.split())


def normalize_paragraphs(text: str):
    """Turn model output into a clean list of plain paragraphs."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\[[^\]]*\]", "", text)  # [stage directions]
    kept = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            kept.append("")
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^[-*\u2022]\s+", "", line)
        line = line.replace("**", "").replace("__", "").replace("*", "")
        if re.match(r"^(scene|chapter|part)\s+\d+\b", line, re.IGNORECASE):
            continue
        line = line.replace("\u2014", ", ").replace("\u2013", ", ")
        line = re.sub(r"\s+,", ",", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        kept.append(line)

    paragraphs, current = [], []
    for line in kept + [""]:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []

    # If the model returned one big block, split it into short paragraphs.
    if len(paragraphs) == 1 and count_words(paragraphs[0]) > 120:
        sentences = re.split(r"(?<=[.!?])\s+", paragraphs[0])
        paragraphs = [
            " ".join(sentences[i:i + 4]) for i in range(0, len(sentences), 4)
        ]
    return [p for p in paragraphs if p]


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


# --------------------------------------------------------------------------
# Outline
# --------------------------------------------------------------------------
OUTLINE_SYSTEM = (
    "You plan calm sleep stories for adults, especially older listeners. "
    "The story is told to the listener in second person, present tense "
    "(you). Nothing dramatic ever happens: no danger, conflict, sadness, "
    "loss, illness, hurry, surprises or frightening images. The mood is "
    "warm, safe, nostalgic and unhurried. Reply with JSON only."
)


def make_outline(seed: dict, previous_titles):
    n = len(SCENE_TARGET_WORDS)
    previous = "; ".join(previous_titles) if previous_titles else "none yet"
    user = (
        "Plan one sleep story.\n"
        f"Idea: {seed['idea']}\n"
        f"Setting: {seed['setting']}\n"
        f"Gentle details to return to again and again: {', '.join(seed['motifs'])}\n"
        f"Earlier story titles (do not repeat their titles or plots): {previous}\n\n"
        "Return JSON in exactly this shape and nothing else:\n"
        '{"title": "<warm, plain title under 60 characters, without the words '
        "'sleep story'>\", "
        '"summary": "<one calm sentence describing the story>", '
        '"scenes": [{"beat": "<one sentence: what gently happens>"}]}\n\n'
        f"The scenes list must contain exactly {n} entries. Scene 1 arrives and "
        "settles in. The middle scenes explore small, comforting details. The "
        "last two scenes become very still and simple. No scene contains "
        "conflict, a problem to solve, or a surprise."
    )
    last_error = "unknown"
    for _ in range(3):
        raw = call_groq(
            [{"role": "system", "content": OUTLINE_SYSTEM},
             {"role": "user", "content": user}],
            max_tokens=1800,
        )
        try:
            data = _extract_json(raw)
            title = str(data["title"]).strip().strip('"')
            beats = [str(s["beat"]).strip() for s in data["scenes"]]
            if len(beats) < n or not title:
                raise ValueError(f"expected {n} scenes, got {len(beats)}")
            return {
                "title": title[:80],
                "summary": str(data.get("summary", "")).strip(),
                "beats": beats[:n],
            }
        except (ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
            print(f"Outline was unusable ({last_error}); asking again")
            time.sleep(GROQ_PAUSE_SECONDS)
    raise GroqError(f"Could not get a usable outline: {last_error}")


# --------------------------------------------------------------------------
# Scenes
# --------------------------------------------------------------------------
SCENE_SYSTEM = (
    "You write sleep stories for adults, especially older listeners, in "
    "second person, present tense (you). Rules:\n"
    "- Calm, warm, unhurried. Use sensory detail: soft sounds, textures, "
    "warmth, gentle smells. Return to the same comforting details.\n"
    "- Nothing dramatic happens. No danger, conflict, sadness, loss, illness, "
    "hurry, surprises, technology, news, money worries or frightening or "
    "violent images.\n"
    "- Use plain, familiar words and short to medium sentences. No slang. "
    "Paragraphs of 3 to 5 sentences.\n"
    "- Invented place names only. No real people, brands, or copyrighted "
    "characters.\n"
    "- The story slowly becomes simpler and quieter as it goes.\n"
    "- Never promise to cure sleep problems or mention medicine.\n"
    "- Output only the story text as plain paragraphs separated by blank "
    "lines. No headings, titles, lists, notes, or markdown."
)


def _pacing_note(index: int, total: int) -> str:
    if index == 0:
        return "Begin by gently arriving in the place and settling in."
    if index == total - 1:
        return (
            "This is the final scene. Make it very still and simple, with "
            "short, quiet sentences that softly repeat earlier details. Let "
            "the story drift into rest and stop. Do not conclude, do not give "
            "a moral, do not say goodbye, and never write 'the end'."
        )
    if index >= total - 3:
        return (
            "Slow down further. Use simpler words and shorter sentences, add "
            "fewer new details, and repeat earlier gentle details."
        )
    return "Keep a slow, gentle pace and linger on small comforting details."


def _last_words(paragraphs, n=110) -> str:
    words = " ".join(paragraphs).split()
    return " ".join(words[-n:])


def write_scene(seed, outline, index, tail):
    total = len(outline["beats"])
    target = SCENE_TARGET_WORDS[index]
    numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(outline["beats"]))
    context = (
        f"The previous scene ended with: \"{tail}\"\nContinue smoothly from "
        "there without repeating it."
        if tail else "This is the opening scene."
    )
    user = (
        f"Story title: {outline['title']}\n"
        f"Setting: {seed['setting']}\n"
        f"Gentle details to return to: {', '.join(seed['motifs'])}\n\n"
        f"Outline:\n{numbered}\n\n"
        f"You are writing scene {index + 1} of {total}: {outline['beats'][index]}\n"
        f"Write about {target} words.\n{context}\n"
        f"{_pacing_note(index, total)}\n"
        "Write only the story text."
    )
    best, best_words = None, 0
    problem = ""
    for attempt in range(3):
        prompt = user if not problem else f"{user}\n\nFix this problem: {problem}"
        raw = call_groq(
            [{"role": "system", "content": SCENE_SYSTEM},
             {"role": "user", "content": prompt}],
            max_tokens=2600,
        )
        paragraphs = normalize_paragraphs(raw)
        text = " ".join(paragraphs)
        words = count_words(text)
        banned = sorted({m.group(0).lower() for m in BANNED_RE.finditer(text)})
        if banned:
            problem = (
                "Your draft used words that do not belong in a calm sleep "
                f"story ({', '.join(banned)}). Rewrite without them."
            )
        elif words < target * 0.7:
            problem = (
                f"Your draft was only {words} words. Write about {target} "
                "words, with more gentle sensory detail."
            )
        elif len(paragraphs) < 3:
            problem = "Use at least 3 paragraphs separated by blank lines."
        else:
            return paragraphs
        print(f"Scene {index + 1} attempt {attempt + 1}: {problem}")
        if not banned and words > best_words and words >= target * 0.55:
            best, best_words = paragraphs, words
        time.sleep(GROQ_PAUSE_SECONDS)
    if best:
        print(f"Scene {index + 1}: using best draft ({best_words} words)")
        return best
    raise GroqError(f"Scene {index + 1} could not be written: {problem}")


def generate_story(seed: dict) -> dict:
    previous = [u.get("title", "") for u in load_used()][-12:]
    outline = make_outline(seed, previous)
    print(f"Title: {outline['title']}")
    scenes, tail = [], ""
    for i in range(len(outline["beats"])):
        time.sleep(GROQ_PAUSE_SECONDS)
        print(f"Writing scene {i + 1}/{len(outline['beats'])}...")
        paragraphs = write_scene(seed, outline, i, tail)
        scenes.append(paragraphs)
        tail = _last_words(paragraphs)
    total_words = sum(count_words(" ".join(p)) for p in scenes)
    print(f"Story written: {total_words} words")
    return {
        "seed_id": seed["id"],
        "title": outline["title"],
        "summary": outline["summary"],
        "scenes": scenes,
        "words": total_words,
    }


def story_to_text(story: dict) -> str:
    parts = [story["title"], story["summary"], ""]
    for i, paragraphs in enumerate(story["scenes"], 1):
        parts.append(f"--- Scene {i} ---")
        parts.append("\n\n".join(paragraphs))
        parts.append("")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Which story is next
# --------------------------------------------------------------------------
def load_used():
    try:
        return json.loads(USED_STORIES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def record_used(seed_id: str, title: str) -> None:
    used = load_used()
    used.append({"seed_id": seed_id, "title": title,
                 "date": time.strftime("%Y-%m-%d")})
    USED_STORIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    USED_STORIES_PATH.write_text(json.dumps(used, indent=2), encoding="utf-8")


def pick_seed() -> dict:
    forced = os.environ.get("STORY_SEED", "").strip()
    if forced:
        for seed in SEEDS:
            if seed["id"] == forced:
                return seed
        ids = ", ".join(s["id"] for s in SEEDS)
        raise ValueError(f"Unknown STORY_SEED '{forced}'. Choose one of: {ids}")
    used_ids = [u.get("seed_id") for u in load_used()]
    for seed in SEEDS:
        if seed["id"] not in used_ids:
            return seed
    return SEEDS[len(used_ids) % len(SEEDS)]
