"""
Central settings for the Nightfern Tales sleep-story pipeline.

Everything you are likely to tweak lives here: the voice, the pacing, the
story seeds, and the video look.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

CHANNEL_NAME = "Nightfern Tales"

# After running src/get_refresh_token.py it prints the channel ID. Put it in
# the EXPECTED_CHANNEL_ID environment variable (or here) so uploads can never
# go to the wrong channel. Leave empty to skip the check.
EXPECTED_CHANNEL_ID = os.environ.get("EXPECTED_CHANNEL_ID", "")

WORKDIR = str(ROOT / "workdir")
REPORTS_DIR = ROOT / "reports"
USED_STORIES_PATH = REPORTS_DIR / "used_stories.json"

# --------------------------------------------------------------------------
# Story writing (Groq free tier). Only these two models exist on the free
# plan. 120b is listed twice so it gets two of every three attempts.
# --------------------------------------------------------------------------
GROQ_MODEL_ORDER = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
)

# Target words per scene. Later scenes are shorter so the story winds down.
# About 4,500 words in total, which is roughly 38-42 minutes when narrated.
SCENE_TARGET_WORDS = [600, 650, 650, 650, 600, 550, 450, 350]

# Pause between Groq calls (seconds). The free tier limits tokens per minute,
# so we space the requests out instead of hammering the API.
GROQ_PAUSE_SECONDS = 18

# --------------------------------------------------------------------------
# Narration (edge-tts, free). Run `python main.py voice-test` to hear the
# candidates and pick one, then set TTS_VOICE here or as an env variable.
# --------------------------------------------------------------------------
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AndrewNeural")
TTS_RATE = os.environ.get("TTS_RATE", "-22%")  # slower than normal speech
PAUSE_PARAGRAPH_SECONDS = 1.8
PAUSE_SCENE_SECONDS = 4.0
END_TAIL_SECONDS = 30  # ambience keeps playing after the last word

VOICE_CANDIDATES = [
    "en-US-AndrewNeural",
    "en-US-ChristopherNeural",
    "en-US-AriaNeural",
    "en-US-JennyNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
]

# --------------------------------------------------------------------------
# Video and sound
# --------------------------------------------------------------------------
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30
CLIP_MAX_SECONDS = 40
CLIPS_WANTED = 12
CLIPS_MINIMUM = 6
VIDEO_CRF = 27

# Level of the soft rain-like noise under the voice (0.0 to 1.0).
# 0.35 puts it about 17 dB below the voice (measured), so the words stay clear
# for older listeners. Raise it if you cannot hear it at all.
BED_VOLUME = float(os.environ.get("BED_VOLUME", "0.35"))

# --------------------------------------------------------------------------
# YouTube
# --------------------------------------------------------------------------
# Start with "private" so you can review each upload. Switch to "public"
# (GitHub repo variable PRIVACY_STATUS) once you trust the output.
PRIVACY_STATUS = os.environ.get("PRIVACY_STATUS", "private")

DISCLAIMER = "This story was written with AI and narrated with a synthetic voice."
SAFETY_LINE = "Please only listen when you are in a place where it is safe to fall asleep."
HASHTAGS = "#sleepstory #bedtimestory #relaxing"
BASE_TAGS = [
    "sleep story",
    "bedtime story for adults",
    "sleep stories for adults",
    "relaxing bedtime story",
    "calm bedtime story",
    "fall asleep",
    "stories to fall asleep to",
    "nightfern tales",
]

# --------------------------------------------------------------------------
# Story seeds: gentle, nostalgic, familiar places for older listeners.
# `keywords` are Pexels search terms; stick to common calm footage.
# --------------------------------------------------------------------------
SEEDS = [
    {
        "id": "night-train",
        "idea": "A slow overnight train through snowy mountains",
        "setting": (
            "a quiet old-fashioned sleeper train gliding through snowy "
            "mountains at night, with a warm compartment, a soft blanket, "
            "a cup of tea, and the steady rhythm of the wheels"
        ),
        "motifs": ["the steady rhythm of the wheels", "snow beyond the window",
                   "a warm blanket", "a cup of tea"],
        "keywords": ["train window snow", "snowy mountains", "train journey landscape",
                     "winter forest", "snow falling", "night train"],
    },
    {
        "id": "seaside-village",
        "idea": "A quiet seaside village at the end of the day",
        "setting": (
            "a small seaside village at evening, with fishing boats resting "
            "in the harbour, a stone path along the shore, soft waves, and "
            "lamplight in cottage windows"
        ),
        "motifs": ["soft waves on the shore", "boats rocking gently",
                   "lamplight in the windows", "the smell of salt and bread"],
        "keywords": ["seaside village", "calm ocean waves", "fishing boats harbor",
                     "coastal path", "sunset beach", "sea at dusk"],
    },
    {
        "id": "lighthouse-evening",
        "idea": "A lighthouse keeper's quiet evening",
        "setting": (
            "a lighthouse on a calm coast at dusk, with a warm kitchen, milk "
            "heating on the stove, a slowly turning lamp, and gentle waves "
            "far below"
        ),
        "motifs": ["the slow turning of the lamp", "warm milk on the stove",
                   "gentle waves below", "a woollen blanket"],
        "keywords": ["lighthouse", "ocean waves evening", "rocky coast",
                     "sea at dusk", "coastal cliffs", "calm sea"],
    },
    {
        "id": "farm-morning",
        "idea": "A farm kitchen before sunrise",
        "setting": (
            "a farmhouse kitchen before sunrise, with bread cooling on the "
            "table, a kettle humming, mist over green fields, and animals "
            "waking slowly in the barn"
        ),
        "motifs": ["fresh bread cooling", "the kettle humming",
                   "mist over the fields", "the quiet barn"],
        "keywords": ["farm morning mist", "countryside fields", "rural barn",
                     "sunrise meadow", "cows pasture", "foggy farm"],
    },
    {
        "id": "rainy-bookshop",
        "idea": "A little bookshop on a rainy evening",
        "setting": (
            "a small old bookshop on a rainy evening, with warm lamps, "
            "creaking wooden shelves, the smell of old paper, a sleepy cat, "
            "and rain tapping softly on the window"
        ),
        "motifs": ["rain tapping the window", "the smell of old paper",
                   "warm lamps", "a sleepy cat"],
        "keywords": ["rain window", "old books library", "rainy street",
                     "cozy interior", "reading lamp", "bookshelf"],
    },
    {
        "id": "country-inn",
        "idea": "A cosy country inn at the end of the valley",
        "setting": (
            "a stone country inn at the end of a green valley, with a "
            "crackling fireplace, a deep armchair, a quilt, and the sound "
            "of a stream outside"
        ),
        "motifs": ["the crackling fireplace", "a patchwork quilt",
                   "a stream outside", "the creak of old beams"],
        "keywords": ["mountain valley", "country road", "fireplace",
                     "stone cottage", "autumn forest", "stream forest"],
    },
    {
        "id": "canal-boat",
        "idea": "A slow canal boat drifting through the countryside",
        "setting": (
            "a painted canal boat moving very slowly along a quiet canal "
            "through green countryside, past willow trees, stone bridges "
            "and grazing sheep"
        ),
        "motifs": ["water lapping the hull", "willow branches trailing",
                   "stone bridges", "the soft hum of the engine"],
        "keywords": ["canal boat", "calm river", "countryside river",
                     "willow trees", "stone bridge", "boat on lake"],
    },
    {
        "id": "evening-garden",
        "idea": "A walk through a quiet garden at dusk",
        "setting": (
            "a walled garden at dusk, with a gravel path, roses and "
            "lavender, a wooden bench, a little pond, and the last light "
            "fading slowly from the sky"
        ),
        "motifs": ["the scent of lavender", "the gravel path underfoot",
                   "a wooden bench", "the fading light"],
        "keywords": ["garden flowers", "garden evening", "sunset garden",
                     "lavender field", "butterfly flowers", "rain on leaves"],
    },
    {
        "id": "forest-cabin",
        "idea": "A small wooden cabin in a rainy forest",
        "setting": (
            "a small wooden cabin in a green forest on a rainy night, with "
            "a woodstove, a thick blanket, a mug of cocoa, and rain falling "
            "softly on the roof"
        ),
        "motifs": ["rain on the roof", "the glow of the woodstove",
                   "a thick blanket", "the scent of pine"],
        "keywords": ["cabin forest", "rain forest", "rain leaves",
                     "forest fog", "wooden cabin", "forest stream"],
    },
    {
        "id": "misty-lake",
        "idea": "A rowing boat on a still lake at dawn",
        "setting": (
            "a small wooden rowing boat resting on a perfectly still lake at "
            "dawn, with soft mist, distant hills, ducks gliding by, and the "
            "sky slowly turning gold"
        ),
        "motifs": ["still water", "soft mist", "ducks gliding by",
                   "the sky turning gold"],
        "keywords": ["calm lake", "lake mist", "rowing boat lake",
                     "mountain lake", "sunrise lake", "ducks lake"],
    },
]
