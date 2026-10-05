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
# About 5,200 words in total, roughly 45-50 minutes when narrated.
SCENE_TARGET_WORDS = [750, 800, 800, 800, 700, 650, 450, 300]
SCENE_MAX_RATIO = 1.45  # a scene longer than this x its target is rewritten shorter

# QUICK_TEST=true makes a short story of about 10 minutes (and never uses up a
# story seed). Handy for checking the voice, the upload, or prompt changes fast.
if os.environ.get("QUICK_TEST", "").strip().lower() in ("1", "true", "yes"):
    SCENE_TARGET_WORDS = [450, 350, 300]

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
VIDEO_FPS = 24  # calm footage does not need more, and it makes rendering faster
CLIP_MAX_SECONDS = 30
CLIPS_WANTED = 24
CLIPS_MINIMUM = 6
VIDEO_CRF = 27

# Night look. Every clip is darkened towards this average brightness (0-255 scale,
# video range) and given a cool moonlight tint, so daytime snow does not glare.
NIGHT_TARGET_LUMA = 46
NIGHT_MIN_FACTOR = 0.40   # never darken a clip below 40% of its original brightness
NIGHT_TINT_BLUE = 6       # moonlight tint: how far colour is pushed towards blue (0 = none)
NIGHT_TINT_WARM = 5       # ...and away from red (0 = none)
# When choosing footage, clips whose preview is brighter than this (0-255) are
# skipped if enough darker ones exist.
MAX_PREVIEW_LUMA = 140

# Soft overlays made by ffmpeg: "snow", "rain", "stars" or "mist" (per story seed).
# Set OVERLAYS=off to disable them everywhere.
OVERLAYS_ENABLED = os.environ.get("OVERLAYS", "on").strip().lower() not in ("off", "0", "false", "no")

# Thumbnail look
THUMB_ART_DIR = ROOT / "assets" / "thumbs"      # optional art per story: <seed id>.jpg / .png
THUMB_FONT = ROOT / "assets" / "fonts" / "NotoSerif-Black.ttf"

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
# Story seeds: gentle, nostalgic, familiar places for older listeners. EVERY story
# takes place at night. `keywords` are Pexels search terms (night-leaning);
# `overlay` is the soft effect laid over the footage.
# --------------------------------------------------------------------------
SEEDS = [
    {
        "id": "night-train",
        "idea": "A slow overnight train through snowy mountains",
        "setting": (
            "a quiet old-fashioned sleeper train gliding through snowy "
            "mountains late at night, with a warm lamplit compartment, a soft "
            "blanket, a cup of tea, a bright moon outside, and the steady "
            "rhythm of the wheels"
        ),
        "motifs": ["the steady rhythm of the wheels", "snow beyond the window",
                   "a warm blanket", "a cup of tea"],
        "keywords": ["night train window snow", "snowy mountains night",
                     "train journey night", "snow falling night",
                     "winter forest night", "moonlit snow"],
        "overlay": "snow",
    },
    {
        "id": "seaside-village",
        "idea": "A quiet seaside village late at night",
        "setting": (
            "a small seaside village late at night, with fishing boats resting "
            "in the moonlit harbour, a stone path along the shore, soft waves, "
            "and lamplight glowing in cottage windows"
        ),
        "motifs": ["soft waves on the shore", "boats rocking gently",
                   "lamplight in the windows", "the smell of salt and bread"],
        "keywords": ["seaside village night", "moonlit sea", "harbor night lights",
                     "night ocean waves", "coastal path night", "starry sky sea"],
        "overlay": "stars",
    },
    {
        "id": "lighthouse-night",
        "idea": "A lighthouse keeper's quiet night",
        "setting": (
            "a lighthouse on a calm coast under a starry night sky, with a "
            "warm kitchen, milk heating on the stove, a slowly turning lamp, "
            "and gentle waves far below"
        ),
        "motifs": ["the slow turning of the lamp", "warm milk on the stove",
                   "gentle waves below", "a woollen blanket"],
        "keywords": ["lighthouse night", "night ocean waves", "moonlit coast",
                     "starry night sea", "coastal cliffs night", "calm sea night"],
        "overlay": "stars",
    },
    {
        "id": "farm-night",
        "idea": "A farm kitchen late at night",
        "setting": (
            "a farmhouse kitchen late at night, with a single lamp glowing, "
            "bread cooling on the table, a kettle humming, moonlight and mist "
            "over the quiet fields, and the animals asleep in the barn"
        ),
        "motifs": ["fresh bread cooling", "the kettle humming",
                   "mist over the moonlit fields", "the sleeping barn"],
        "keywords": ["farm night", "countryside night", "barn night",
                     "moonlit field", "night fog fields", "starry sky countryside"],
        "overlay": "mist",
    },
    {
        "id": "rainy-bookshop",
        "idea": "A little bookshop on a rainy night",
        "setting": (
            "a small old bookshop late on a rainy night, with warm lamps, "
            "creaking wooden shelves, the smell of old paper, a sleepy cat, "
            "and rain tapping softly on the window"
        ),
        "motifs": ["rain tapping the window", "the smell of old paper",
                   "warm lamps", "a sleepy cat"],
        "keywords": ["rain window night", "rainy night street", "old books night",
                     "cozy night lamp", "night rain city", "bookshelf warm light"],
        "overlay": "rain",
    },
    {
        "id": "country-inn",
        "idea": "A cosy country inn at the end of the valley, at night",
        "setting": (
            "a stone country inn at the end of a quiet valley on a still "
            "night, with a crackling fireplace, a deep armchair, a quilt, "
            "valley mist under the moon, and the sound of a stream outside"
        ),
        "motifs": ["the crackling fireplace", "a patchwork quilt",
                   "a stream outside", "the creak of old beams"],
        "keywords": ["mountain valley night", "country road night", "fireplace",
                     "stone cottage night", "night forest", "stream night"],
        "overlay": "mist",
    },
    {
        "id": "canal-boat",
        "idea": "A slow canal boat drifting through the countryside at night",
        "setting": (
            "a painted canal boat moving very slowly along a quiet canal "
            "through moonlit countryside at night, past willow trees, stone "
            "bridges and sleeping fields, with a small lantern glowing at the bow"
        ),
        "motifs": ["water lapping the hull", "willow branches trailing",
                   "stone bridges", "the soft hum of the engine"],
        "keywords": ["canal night", "river night calm", "moonlit river",
                     "willow trees night", "stone bridge night", "boat night lights"],
        "overlay": "mist",
    },
    {
        "id": "night-garden",
        "idea": "A walk through a quiet garden at night",
        "setting": (
            "a walled garden at night under a bright moon, with a gravel "
            "path, roses and lavender, a wooden bench, a still pond, and "
            "stars shining above the old stone wall"
        ),
        "motifs": ["the scent of lavender", "the gravel path underfoot",
                   "a wooden bench", "moonlight on the pond"],
        "keywords": ["garden night", "moonlit garden", "night flowers",
                     "garden lights night", "lavender night", "rain on leaves night"],
        "overlay": "stars",
    },
    {
        "id": "forest-cabin",
        "idea": "A small wooden cabin in a rainy forest at night",
        "setting": (
            "a small wooden cabin in a green forest on a rainy night, with "
            "a woodstove, a thick blanket, a mug of cocoa, and rain falling "
            "softly on the roof"
        ),
        "motifs": ["rain on the roof", "the glow of the woodstove",
                   "a thick blanket", "the scent of pine"],
        "keywords": ["cabin forest night", "rain forest night", "night rain leaves",
                     "forest fog night", "wooden cabin night", "forest stream night"],
        "overlay": "rain",
    },
    {
        "id": "moonlit-lake",
        "idea": "A rowing boat on a still lake under the moon",
        "setting": (
            "a small wooden rowing boat resting on a perfectly still lake "
            "under a full moon, with soft mist, distant dark hills, ducks "
            "asleep on the shore, and stars reflected in the water"
        ),
        "motifs": ["still water", "the moon's reflection", "soft mist",
                   "stars on the water"],
        "keywords": ["lake night", "moonlit lake", "mountain lake night",
                     "starry night lake", "lake mist night", "calm water night"],
        "overlay": "stars",
    },
]
