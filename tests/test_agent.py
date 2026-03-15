"""Tests for agent.py — MCP server detection and run logic."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent import build_mcp_servers, run


# ---------------------------------------------------------------------------
# build_mcp_servers
# ---------------------------------------------------------------------------

class TestBuildMcpServers:
    def test_detects_prefixed_vars(self):
        env = {
            "MCP_SERVER_SLACK": "https://slack-mcp.example.com/sse",
            "MCP_SERVER_GITHUB": "https://github-mcp.example.com/sse",
            "OTHER_VAR": "ignored",
        }
        with patch.dict(os.environ, env, clear=True):
            servers = build_mcp_servers()

        names = {s["name"] for s in servers}
        assert names == {"slack", "github"}
        for s in servers:
            assert s["type"] == "url"
            assert s["url"].startswith("https://")

    def test_empty_when_no_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            assert build_mcp_servers() == []

    def test_name_lowercased(self):
        with patch.dict(os.environ, {"MCP_SERVER_FOO_BAR": "https://x.com/sse"}, clear=True):
            servers = build_mcp_servers()
            assert servers[0]["name"] == "foo_bar"


# ---------------------------------------------------------------------------
# run (end-to-end with mocks)
# ---------------------------------------------------------------------------

class TestRun:
    @patch("agent.anthropic.Anthropic")
    @patch("agent.fetch_thread")
    @patch("agent.parse_slack_link")
    def test_returns_draft_text(self, mock_parse, mock_fetch, mock_anthropic_cls):
        mock_parse.return_value = ("C123", "1700000000.123456")
        mock_fetch.return_value = ("<U001> Help me", [])

        # Mock Claude response
        mock_block = SimpleNamespace(type="text", text="[초안]\n답변 내용입니다.")
        mock_response = SimpleNamespace(content=[mock_block])
        mock_client = MagicMock()
        mock_client.beta.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        result = run("https://team.slack.com/archives/C123/p1700000000123456")

        assert "[초안]" in result
        assert "답변 내용입니다." in result

    @patch("agent.anthropic.Anthropic")
    @patch("agent.fetch_thread")
    @patch("agent.parse_slack_link")
    def test_includes_images_in_content(self, mock_parse, mock_fetch, mock_anthropic_cls):
        mock_parse.return_value = ("C123", "1700000000.123456")
        image_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "abc="},
        }
        mock_fetch.return_value = ("<U001> See screenshot", [image_block])

        mock_block = SimpleNamespace(type="text", text="Draft")
        mock_response = SimpleNamespace(content=[mock_block])
        mock_client = MagicMock()
        mock_client.beta.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        run("https://team.slack.com/archives/C123/p1700000000123456")

        # Verify image block was passed to Claude
        call_kwargs = mock_client.beta.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert user_content[0] == image_block
        assert user_content[1]["type"] == "text"

    @patch("agent.anthropic.Anthropic")
    @patch("agent.fetch_thread")
    @patch("agent.parse_slack_link")
    def test_mcp_servers_passed_when_configured(
        self, mock_parse, mock_fetch, mock_anthropic_cls
    ):
        mock_parse.return_value = ("C123", "1700000000.123456")
        mock_fetch.return_value = ("<U001> Q", [])

        mock_block = SimpleNamespace(type="text", text="A")
        mock_response = SimpleNamespace(content=[mock_block])
        mock_client = MagicMock()
        mock_client.beta.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        env = {"MCP_SERVER_TEST": "https://test.example.com/sse"}
        with patch.dict(os.environ, env):
            run("https://team.slack.com/archives/C123/p1700000000123456")

        call_kwargs = mock_client.beta.messages.create.call_args.kwargs
        assert "mcp_servers" in call_kwargs
        assert call_kwargs["mcp_servers"][0]["name"] == "test"
        assert call_kwargs["tools"][0]["type"] == "mcp_toolset"

    @patch("agent.anthropic.Anthropic")
    @patch("agent.fetch_thread")
    @patch("agent.parse_slack_link")
    def test_no_mcp_servers_when_unconfigured(
        self, mock_parse, mock_fetch, mock_anthropic_cls
    ):
        mock_parse.return_value = ("C123", "1700000000.123456")
        mock_fetch.return_value = ("<U001> Q", [])

        mock_block = SimpleNamespace(type="text", text="A")
        mock_response = SimpleNamespace(content=[mock_block])
        mock_client = MagicMock()
        mock_client.beta.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        with patch.dict(os.environ, {}, clear=True):
            # Restore ANTHROPIC_API_KEY so client init doesn't fail
            os.environ["ANTHROPIC_API_KEY"] = "test"
            run("https://team.slack.com/archives/C123/p1700000000123456")

        call_kwargs = mock_client.beta.messages.create.call_args.kwargs
        assert "mcp_servers" not in call_kwargs
        assert "tools" not in call_kwargs
