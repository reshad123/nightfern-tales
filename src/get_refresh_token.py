"""
Run this ONCE on your own computer to log in and get the YouTube refresh token.

    python src/get_refresh_token.py

Needs client_secret.json (OAuth client of type "Desktop app") in the project
folder. A browser opens: sign in with the Google account that owns the channel
and, if asked, PICK THE NIGHTFERN TALES CHANNEL. The values are written to
.env with no quotes, so you can copy them straight into GitHub secrets.
"""

import sys
from pathlib import Path

import requests
from dotenv import dotenv_values, set_key
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def main():
    secret_file = ROOT / "client_secret.json"
    if not secret_file.exists():
        sys.exit(f"Put client_secret.json in {ROOT} first (see README step 2).")

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
    print("A browser window will open. Sign in and pick the channel you want to upload to.")
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit(
            "Google did not return a refresh token. Remove this app from "
            "https://myaccount.google.com/permissions and run this again."
        )

    resp = requests.get(
        CHANNELS_URL,
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    if not items:
        sys.exit("This Google login has no YouTube channel. Create the channel first.")
    channel_id = items[0]["id"]
    title = items[0]["snippet"]["title"]
    print(f"\nLogged in to channel: {title}  ({channel_id})")

    env_path = ROOT / ".env"
    env_path.touch(exist_ok=True)
    values = {
        "YT_CLIENT_ID": creds.client_id,
        "YT_CLIENT_SECRET": creds.client_secret,
        "YT_REFRESH_TOKEN": creds.refresh_token,
        "EXPECTED_CHANNEL_ID": channel_id,
    }
    for key, value in values.items():
        set_key(str(env_path), key, value, quote_mode="never")

    saved = dotenv_values(env_path)
    for key in values:
        if not saved.get(key):
            sys.exit(f"{key} did not get saved to .env. Please run this again.")
    print(f"Saved to {env_path}:")
    for key in values:
        print(f"  {key}: saved ({len(saved[key])} characters)")

    print(
        "\nNext: in your GitHub repo add these as Actions SECRETS (copy the values "
        "from .env, with no quotes):\n  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN"
        "\nand this as an Actions VARIABLE:\n  EXPECTED_CHANNEL_ID"
        f"  (value: {channel_id})"
    )


if __name__ == "__main__":
    main()
