#!/usr/bin/env python3
"""Slack draft agent - CLI tool for drafting replies to Slack technical inquiries."""

import os
import sys

import anthropic
from dotenv import load_dotenv

from slack_client import fetch_thread, parse_slack_link, send_dm

load_dotenv()

SYSTEM_PROMPT = """\
당신은 슬랙에 올라오는 기술 문의에 대해 답변 초안을 작성하는 에이전트입니다.

답변 작성 순서:
1. 첨부 이미지가 있으면 화면에서 이상 지표·수치를 먼저 파악하세요.
2. 등록된 MCP 서버를 활용해 관련 데이터와 컨텍스트를 수집하세요.
   (이전 답변 검색, 관련 지표 조회, 코드·PR 확인 등)
3. 수집한 정보를 종합해 명확하고 간결한 답변 초안을 작성하세요.

출력 형식:
---
[초안]
(슬랙에 바로 붙여넣을 수 있는 답변)

[근거]
- 사용한 데이터 출처와 핵심 수치

[참고 링크]
- 관련 스레드 / PR / 문서 URL
---

확실하지 않은 내용은 추측하지 말고 "확인 필요"로 표시하세요."""

MODEL = "claude-sonnet-4-6"


def build_mcp_servers() -> list[dict]:
    """Auto-detect MCP_SERVER_ prefixed env vars and build server definitions."""
    return [
        {"type": "url", "url": url, "name": key.replace("MCP_SERVER_", "").lower()}
        for key, url in os.environ.items()
        if key.startswith("MCP_SERVER_")
    ]


def run(link: str) -> str:
    """Fetch thread, call Claude with MCP + Vision, return draft text."""
    channel_id, thread_ts = parse_slack_link(link)
    print(f"Fetching thread: channel={channel_id}, ts={thread_ts}")

    thread_text, image_blocks = fetch_thread(channel_id, thread_ts)
    print(f"Thread loaded: {len(thread_text)} chars, {len(image_blocks)} image(s)")

    # Build user content: images first, then text
    content: list[dict] = []
    content.extend(image_blocks)
    content.append(
        {
            "type": "text",
            "text": f"아래 슬랙 스레드에 대한 답변 초안을 작성해주세요.\n\n{thread_text}",
        }
    )

    # Build MCP config
    mcp_servers = build_mcp_servers()
    tools = [
        {"type": "mcp_toolset", "mcp_server_name": s["name"]} for s in mcp_servers
    ]

    if mcp_servers:
        print(f"MCP servers: {[s['name'] for s in mcp_servers]}")
    else:
        print("No MCP servers configured.")

    # Call Claude
    client = anthropic.Anthropic()

    kwargs: dict = {
        "model": MODEL,
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": content}],
        "betas": ["mcp-client-2025-11-20"],
    }
    if mcp_servers:
        kwargs["mcp_servers"] = mcp_servers
        kwargs["tools"] = tools

    print("Calling Claude...")
    response = client.beta.messages.create(**kwargs)

    # Extract text blocks from response
    text_parts: list[str] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    return "\n".join(text_parts)


def main() -> None:
    if len(sys.argv) > 1:
        link = sys.argv[1]
    else:
        link = input("Slack link: ").strip()

    if not link:
        print("No link provided.")
        sys.exit(1)

    try:
        draft = run(link)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + draft)

    # Send draft to own DM
    my_user_id = os.environ.get("MY_SLACK_USER_ID", "")
    if my_user_id:
        print("\nSending draft to your DM...")
        send_dm(my_user_id, draft)
        print("Done!")
    else:
        print("\nMY_SLACK_USER_ID not set. Skipping DM.")


if __name__ == "__main__":
    main()
