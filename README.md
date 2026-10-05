# Nightfern Tales: sleep-story video pipeline

Writes a calm 35-45 minute sleep story with Groq (free), narrates it with
edge-tts (free), lays it over slow Pexels footage with a soft rain-like noise
bed, and uploads it to YouTube. It runs on GitHub Actions, like your other
channels. Everything is free.

**It starts in "dry run" mode.** Nothing is uploaded until you have listened to
a story and turned uploading on yourself.

## One-time setup

### 1. Keys you already have
`GROQ_API_KEY` and `PEXELS_API_KEY`: reuse the ones from your other channels.

### 2. The YouTube channel
1. Create the **Nightfern Tales** channel (a separate Google account is the
   safer choice, so it is isolated from How Come?).
2. If you use a new Google account: Google Cloud Console, your existing project,
   **Audience > Test users > Add users**, and add that account's email.
3. Phone-verify the channel at youtube.com/verify (needed for videos over 15 minutes).
4. Reuse your existing Desktop OAuth client. Create `client_secret.json` in this
   folder (Google no longer lets you download it, so build it by hand):

```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost"]
  }
}
```

5. On your computer, inside this folder:

```
pip install -r requirements.txt
python src/get_refresh_token.py
```

   Sign in, and **pick the Nightfern Tales channel** if asked. It prints the
   channel and saves four values into `.env` (no quotes, and it checks they saved).

### 3. Put the code on GitHub (use git, not drag-and-drop)
Drag-and-drop skips the hidden `.github` folder, which is where the workflow lives.

Create an empty repository on GitHub (private is fine; private repos get 2,000 free
Actions minutes a month), then in this folder:

```
git init
git add .
git commit -m "Nightfern Tales"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/nightfern-tales.git
git push -u origin main
```

`.gitignore` already keeps `.env` and `client_secret.json` out of the repo.

### 4. Add secrets and variables
Repo > Settings > Secrets and variables > Actions.

**Secrets** (exact names, raw values from `.env`, no quotes):
`GROQ_API_KEY`, `PEXELS_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`

**Variables** (Variables tab):
- `EXPECTED_CHANNEL_ID` = the channel ID the token script printed (stops uploads going to the wrong channel)
- `PRIVACY_STATUS` = `private` for now (later `public`)
- `TTS_VOICE` = optional, see "Choosing the voice"

## First run (dry run)
1. Actions tab > **Nightfern Story** > **Run workflow**, leave "Upload" **off**, run it.
2. When it finishes, open the run and download the **review-...** file at the bottom.
   It holds `story.txt` (read it), `mix.m4a` (the full audio, listen to it),
   `preview.mp4` (the first 3 minutes) and `thumbnail.jpg`.
3. If something fails, send me the log and I will fix it.

For a cheaper first check of just the writing, run locally: `python main.py story-only`.

## Choosing the voice
`python main.py voice-test` makes a short sample of six voices in `workdir/voice_samples`.
Listen, then set the `TTS_VOICE` repo variable (or `TTS_VOICE` in `config.py`).

## Going live
1. Run once with **Upload on**. It uploads as **private**. Check it in YouTube Studio.
2. Happy? Set the `PRIVACY_STATUS` variable to `public`.
3. In `.github/workflows/story.yml`, remove the `#` from the two `schedule:` lines
   and commit. It then makes one story a day.

## Things to know
- **Refresh token.** While your Google Cloud consent screen is in Testing mode, the
  token expires after 7 days: run `get_refresh_token.py` again and update
  `YT_REFRESH_TOKEN`. The error message says so.
- **Disclosure.** Every description says the story is AI-written with a synthetic
  voice (`DISCLAIMER` in `config.py`).
- **Policy risk.** YouTube de-monetizes mass-produced, templated content. Keep an
  eye on Studio, and keep uploads private until you are comfortable.
- **Sound.** The background is generated noise, so there are no music licensing claims.
- **Thumbnails** are made automatically (`thumbnail.jpg` is in the review files) and set after
  upload. Custom thumbnails need the channel to be phone-verified; if YouTube refuses, the log
  says so and you can upload `thumbnail.jpg` by hand in Studio.
- **Not automated yet.** An intro/outro.

## Tuning (all in `config.py`)
| Setting | What it does |
|---|---|
| `SEEDS` | The story ideas. Add your own; each is used once, in order. |
| `SCENE_TARGET_WORDS` | Story length. About 125 words per narrated minute. |
| `TTS_VOICE`, `TTS_RATE` | Voice and speaking speed (`-22%` is slower than normal). |
| `BED_VOLUME` | Rain-noise level. Raise it if you cannot hear it. |
| `CLIPS_WANTED`, `CLIP_MAX_SECONDS` | How much footage is used before it repeats. |
