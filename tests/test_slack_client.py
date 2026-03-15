"""Tests for slack_client.py — link parsing, thread fetching, DM sending."""

import base64
from unittest.mock import patch

import httpx
import pytest

from slack_client import fetch_thread, parse_slack_link, send_dm


# ---------------------------------------------------------------------------
# parse_slack_link
# ---------------------------------------------------------------------------

class TestParseSlackLink:
    def test_parent_message(self):
        link = "https://myteam.slack.com/archives/C01AB23CD/p1700000000123456"
        channel, ts = parse_slack_link(link)
        assert channel == "C01AB23CD"
        assert ts == "1700000000.123456"

    def test_reply_with_thread_ts(self):
        link = (
            "https://myteam.slack.com/archives/C01AB23CD/p1700000000999999"
            "?thread_ts=1700000000.123456&cid=C01AB23CD"
        )
        channel, ts = parse_slack_link(link)
        assert channel == "C01AB23CD"
        # thread_ts from query param (parent) is used
        assert ts == "1700000000.123456"

    def test_private_channel(self):
        link = "https://myteam.slack.com/archives/G01AB23CD/p1700000000123456"
        channel, ts = parse_slack_link(link)
        assert channel == "G01AB23CD"

    def test_invalid_link_raises(self):
        with pytest.raises(ValueError, match="Invalid Slack link"):
            parse_slack_link("https://example.com/not-a-slack-link")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_slack_link("")


# ---------------------------------------------------------------------------
# fetch_thread
# ---------------------------------------------------------------------------

def _mock_slack_response(messages, ok=True):
    """Create a mock httpx.Response for Slack API."""
    payload = {"ok": ok, "messages": messages}
    if not ok:
        payload["error"] = "channel_not_found"
    return httpx.Response(200, json=payload)


def _mock_image_response(content: bytes = b"\x89PNG\r\n"):
    return httpx.Response(200, content=content)


class TestFetchThread:
    @patch("slack_client.httpx.get")
    def test_text_only(self, mock_get):
        mock_get.return_value = _mock_slack_response(
            [
                {"user": "U001", "text": "Help me with X"},
                {"user": "U002", "text": "Have you tried Y?"},
            ]
        )

        text, images = fetch_thread("C123", "1700000000.123456")

        assert "<U001> Help me with X" in text
        assert "<U002> Have you tried Y?" in text
        assert images == []

    @patch("slack_client.httpx.get")
    def test_with_image(self, mock_get):
        fake_png = b"\x89PNG_FAKE"

        def side_effect(url, **kwargs):
            if "conversations.replies" in url:
                return _mock_slack_response(
                    [
                        {
                            "user": "U001",
                            "text": "See screenshot",
                            "files": [
                                {
                                    "mimetype": "image/png",
                                    "url_private": "https://files.slack.com/img.png",
                                }
                            ],
                        }
                    ]
                )
            # Image download
            return _mock_image_response(fake_png)

        mock_get.side_effect = side_effect

        text, images = fetch_thread("C123", "1700000000.123456")

        assert "<U001> See screenshot" in text
        assert len(images) == 1
        assert images[0]["type"] == "image"
        assert images[0]["source"]["media_type"] == "image/png"
        decoded = base64.standard_b64decode(images[0]["source"]["data"])
        assert decoded == fake_png

    @patch("slack_client.httpx.get")
    def test_non_image_file_skipped(self, mock_get):
        mock_get.return_value = _mock_slack_response(
            [
                {
                    "user": "U001",
                    "text": "Here is a doc",
                    "files": [
                        {
                            "mimetype": "application/pdf",
                            "url_private": "https://files.slack.com/doc.pdf",
                        }
                    ],
                }
            ]
        )

        _, images = fetch_thread("C123", "1700000000.123456")
        assert images == []

    @patch("slack_client.httpx.get")
    def test_api_error_raises(self, mock_get):
        mock_get.return_value = _mock_slack_response([], ok=False)

        with pytest.raises(RuntimeError, match="Slack API error"):
            fetch_thread("C123", "1700000000.123456")


# ---------------------------------------------------------------------------
# send_dm
# ---------------------------------------------------------------------------

class TestSendDm:
    @patch("slack_client.httpx.post")
    def test_success(self, mock_post):
        mock_post.side_effect = [
            # conversations.open
            httpx.Response(200, json={"ok": True, "channel": {"id": "D999"}}),
            # chat.postMessage
            httpx.Response(200, json={"ok": True}),
        ]

        send_dm("U001", "Hello!")

        assert mock_post.call_count == 2
        # Verify conversations.open was called with correct user
        open_call = mock_post.call_args_list[0]
        assert open_call.kwargs["json"]["users"] == "U001"
        # Verify chat.postMessage was called with correct channel and text
        post_call = mock_post.call_args_list[1]
        assert post_call.kwargs["json"]["channel"] == "D999"
        assert post_call.kwargs["json"]["text"] == "Hello!"

    @patch("slack_client.httpx.post")
    def test_open_error_raises(self, mock_post):
        mock_post.return_value = httpx.Response(
            200, json={"ok": False, "error": "user_not_found"}
        )

        with pytest.raises(RuntimeError, match="conversations.open error"):
            send_dm("UBAD", "Hello!")

    @patch("slack_client.httpx.post")
    def test_post_error_raises(self, mock_post):
        mock_post.side_effect = [
            httpx.Response(200, json={"ok": True, "channel": {"id": "D999"}}),
            httpx.Response(200, json={"ok": False, "error": "channel_not_found"}),
        ]

        with pytest.raises(RuntimeError, match="chat.postMessage error"):
            send_dm("U001", "Hello!")
