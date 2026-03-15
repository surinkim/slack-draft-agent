"""Slack API helpers: thread reading, image downloading, DM sending."""

import base64
import os
import re
import urllib.parse

import httpx

SLACK_API = "https://slack.com/api"
_TIMEOUT = 60.0


def _get_token() -> str:
    return os.environ.get("SLACK_USER_TOKEN", "")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_token()}"}


def parse_slack_link(link: str) -> tuple[str, str]:
    """Parse channel_id and thread_ts from a Slack message link.

    Handles both thread parent and reply links.
    p1234567890123456 -> 1234567890.123456
    """
    parsed = urllib.parse.urlparse(link)
    params = urllib.parse.parse_qs(parsed.query)

    match = re.search(r"/archives/([A-Z0-9]+)/p(\d{10})(\d{6})", link)
    if not match:
        raise ValueError(f"Invalid Slack link: {link}")

    channel_id = match.group(1)
    message_ts = f"{match.group(2)}.{match.group(3)}"

    # Reply links have ?thread_ts= pointing to the parent message
    thread_ts = params.get("thread_ts", [message_ts])[0]
    return channel_id, thread_ts


def fetch_thread(channel_id: str, thread_ts: str) -> tuple[str, list[dict]]:
    """Fetch full thread via conversations.replies.

    Returns:
        thread_text: newline-joined thread messages
        image_blocks: Claude Vision content blocks (base64-encoded images)
    """
    resp = httpx.get(
        f"{SLACK_API}/conversations.replies",
        headers=_headers(),
        params={"channel": channel_id, "ts": thread_ts},
        timeout=_TIMEOUT,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")

    messages = data.get("messages", [])
    lines: list[str] = []
    image_blocks: list[dict] = []

    for msg in messages:
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        lines.append(f"<{user}> {text}")

        for f in msg.get("files", []):
            mime = f.get("mimetype", "")
            if not mime.startswith("image/"):
                continue
            url = f.get("url_private", "")
            if not url:
                continue
            img_resp = httpx.get(url, headers=_headers(), timeout=_TIMEOUT)
            if img_resp.status_code != 200:
                continue
            b64 = base64.standard_b64encode(img_resp.content).decode()
            image_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": b64,
                    },
                }
            )

    return "\n".join(lines), image_blocks


def send_dm(user_id: str, text: str) -> None:
    """Open a DM channel with user_id and send text."""
    # Open DM channel
    open_resp = httpx.post(
        f"{SLACK_API}/conversations.open",
        headers=_headers(),
        json={"users": user_id},
        timeout=_TIMEOUT,
    )
    open_data = open_resp.json()
    if not open_data.get("ok"):
        raise RuntimeError(f"conversations.open error: {open_data.get('error')}")

    dm_channel = open_data["channel"]["id"]

    # Send message
    post_resp = httpx.post(
        f"{SLACK_API}/chat.postMessage",
        headers=_headers(),
        json={"channel": dm_channel, "text": text},
        timeout=_TIMEOUT,
    )
    post_data = post_resp.json()
    if not post_data.get("ok"):
        raise RuntimeError(f"chat.postMessage error: {post_data.get('error')}")
