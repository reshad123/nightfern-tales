"""Quick check of the YouTube login, no video needed. Run from the project folder:
    python check_upload_auth.py
It reads .env, prints which permissions the token really has, and asks YouTube to
START an upload (nothing is uploaded, nothing is published)."""
import json, os, requests
from dotenv import load_dotenv

load_dotenv()
r = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
    "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
print("1. token refresh:", r.status_code)
if r.status_code != 200:
    raise SystemExit(r.text)
tok = r.json()["access_token"]
print("   scope in refresh answer:", r.json().get("scope"))

t = requests.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": tok}, timeout=30)
print("2. tokeninfo:", t.status_code, t.text[:400].replace("\n", " "))

c = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "id,snippet", "mine": "true"},
                 headers={"Authorization": f"Bearer {tok}"}, timeout=30)
items = c.json().get("items") or [{}]
print("3. channel read:", c.status_code, items[0].get("id"), (items[0].get("snippet") or {}).get("title"))

meta = {"snippet": {"title": "auth test", "categoryId": "24"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
i = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                  data=json.dumps(meta), timeout=60, headers={
                      "Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                      "X-Upload-Content-Length": "1000000", "X-Upload-Content-Type": "video/mp4"})
print("4. start upload:", i.status_code, "OK, session created" if i.status_code == 200 else i.text[:300])
