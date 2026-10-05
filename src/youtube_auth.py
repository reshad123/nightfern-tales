"""YouTube OAuth helpers: refresh the access token and check the channel."""

import os

import requests

from config import CHANNEL_NAME, EXPECTED_CHANNEL_ID

TOKEN_URL = "https://oauth2.googleapis.com/token"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def get_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["YT_CLIENT_ID"],
            "client_secret": os.environ["YT_CLIENT_SECRET"],
            "refresh_token": os.environ["YT_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        hint = ""
        if "invalid_grant" in resp.text:
            hint = (
                " The refresh token has expired or been revoked. While the "
                "Google Cloud consent screen is in Testing mode, tokens expire "
                "after 7 days: run src/get_refresh_token.py again and update "
                "the YT_REFRESH_TOKEN secret."
            )
        raise RuntimeError(f"Token refresh failed ({resp.status_code}): {resp.text[:300]}.{hint}")
    return resp.json()["access_token"]


def fetch_channel(token: str) -> dict:
    resp = requests.get(
        CHANNELS_URL,
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    if not items:
        raise RuntimeError("No YouTube channel found for this login.")
    return items[0]


def require_expected_channel(token: str = None) -> dict:
    """Print the logged-in channel, and stop if it is not the expected one."""
    channel = fetch_channel(token or get_access_token())
    channel_id = channel.get("id", "")
    title = (channel.get("snippet") or {}).get("title", "")
    print(f"YouTube login: {title} ({channel_id})")
    if EXPECTED_CHANNEL_ID and channel_id != EXPECTED_CHANNEL_ID:
        raise RuntimeError(
            f"Logged into '{title}' ({channel_id}) but expected {CHANNEL_NAME} "
            f"({EXPECTED_CHANNEL_ID}). Run src/get_refresh_token.py again and "
            "pick the right channel, then update the YT_REFRESH_TOKEN secret."
        )
    return channel
