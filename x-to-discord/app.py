import os
import time
import json
import logging
from pathlib import Path

import requests
from flask import Flask, jsonify

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

X_BEARER_TOKEN = os.environ["X_BEARER_TOKEN"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
X_USERNAME = os.getenv("X_USERNAME", "itsyourfatb0i").lstrip("@")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
INCLUDE_REPLIES = os.getenv("INCLUDE_REPLIES", "false").lower() == "true"
STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))

app = Flask(__name__)

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {X_BEARER_TOKEN}",
    "User-Agent": "x-to-discord/1.0",
})

def x_get(url, params=None):
    r = session.get(url, params=params, timeout=30)
    if r.status_code == 429:
        raise RuntimeError("X API rate limit reached")
    r.raise_for_status()
    return r.json()

def discord_post(payload):
    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )
    if r.status_code == 429:
        retry_after = r.json().get("retry_after", 1)
        logging.warning("Discord rate limited; waiting %.2fs", retry_after)
        time.sleep(float(retry_after))
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
    r.raise_for_status()

def get_user_id():
    data = x_get(f"https://api.x.com/2/users/by/username/{X_USERNAME}")
    return data["data"]["id"], data["data"]

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state))

def search_posts(since_id=None):
    query = f"from:{X_USERNAME} -is:retweet"
    if not INCLUDE_REPLIES:
        query += " -is:reply"

    params = {
        "query": query,
        "max_results": 10,
        "tweet.fields": "created_at,author_id,attachments",
        "expansions": "attachments.media_keys",
        "media.fields": "url,preview_image_url,type",
    }
    if since_id:
        params["since_id"] = since_id

    return x_get("https://api.x.com/2/tweets/search/recent", params)

def send_post(tweet):
    tweet_id = tweet["id"]
    text = tweet.get("text", "")
    created_at = tweet.get("created_at", "")

    # Discord embeds have a 4096-char description limit.
    if len(text) > 4000:
        text = text[:3997] + "..."

    payload = {
        "username": f"X Feed • @{X_USERNAME}",
        "embeds": [{
            "author": {
                "name": f"@{X_USERNAME}",
                "url": f"https://x.com/{X_USERNAME}",
            },
            "description": text or "(media-only post)",
            "url": f"https://x.com/{X_USERNAME}/status/{tweet_id}",
            "timestamp": created_at,
            "footer": {"text": "X → Discord"},
        }]
    }

    discord_post(payload)
    logging.info("Sent X post %s to Discord", tweet_id)

def worker():
    state = load_state()

    # Resolve username once at startup.
    user_id, user = get_user_id()
    logging.info("Watching @%s (user id %s)", user["username"], user_id)

    # On first run, establish a baseline so old posts are NOT dumped into Discord.
    if not state.get("since_id"):
        result = search_posts()
        posts = result.get("data", [])
        if posts:
            newest = max(posts, key=lambda p: int(p["id"]))
            state["since_id"] = newest["id"]
            save_state(state)
            logging.info("Baseline set at post %s; no old posts sent.", newest["id"])
        else:
            logging.info("No recent posts found; starting without a baseline.")

    while True:
        try:
            result = search_posts(state.get("since_id"))
            posts = result.get("data", [])

            # API returns newest-first. Send oldest-first if multiple appeared.
            posts.sort(key=lambda p: int(p["id"]))

            for post in posts:
                send_post(post)
                state["since_id"] = post["id"]
                save_state(state)

        except Exception:
            logging.exception("Polling failed")

        time.sleep(POLL_SECONDS)

@app.get("/")
def health():
    return jsonify({
        "ok": True,
        "watching": f"@{X_USERNAME}",
        "poll_seconds": POLL_SECONDS,
        "include_replies": INCLUDE_REPLIES,
    })

if __name__ == "__main__":
    import threading
    threading.Thread(target=worker, daemon=True).start()
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
