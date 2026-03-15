# slack-draft-agent

**English** | [한국어](./README_ko.md)

An agent that reads Slack technical inquiry threads, automatically gathers relevant context, drafts a reply, and sends it to your own DM for review.

## Features

- Read full Slack threads including replies
- Analyze attached images (Claude Vision)
- Gather context via MCP servers (search past answers, query metrics, check code/PRs, etc.)
- Send draft to your own DM (human reviews and posts manually)

## Installation

```bash
git clone https://github.com/surinkim/slack-draft-agent.git
cd slack-draft-agent
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in the values.

```bash
cp .env.example .env
```

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Slack
SLACK_USER_TOKEN=xoxp-...        # User Token (read threads, download images, send DMs)
MY_SLACK_USER_ID=U...            # Your Slack user ID to receive drafts
```

### Required Slack User Token scopes

- `channels:history` — Read public channel threads
- `groups:history` — Read private channel threads
- `files:read` — Download attached images
- `im:write` — Open DM channels
- `chat:write` — Send DMs

## Adding MCP servers

Add environment variables prefixed with `MCP_SERVER_` in `.env` to connect MCP servers automatically.

```env
MCP_SERVER_SLACK=https://your-slack-mcp-server/sse
MCP_SERVER_GITHUB=https://your-github-mcp-server/sse
MCP_SERVER_FOO=https://your-custom-mcp-server/sse
```

The server name is derived by stripping the `MCP_SERVER_` prefix and lowercasing.
e.g. `MCP_SERVER_GITHUB` → server name `github`

## Usage

```bash
# Pass link as argument
python agent.py "https://your-workspace.slack.com/archives/C01234567/p1234567890123456"

# Interactive input
python agent.py
Slack link: https://your-workspace.slack.com/archives/C01234567/p1234567890123456
```

### Example output

```
Fetching thread: channel=C01234567, ts=1234567890.123456
Thread loaded: 523 chars, 1 image(s)
MCP servers: ['slack', 'github']
Calling Claude...

---
[Draft]
(Reply ready to paste into Slack)

[Evidence]
- Data sources and key metrics used

[References]
- Related threads / PRs / doc URLs
---

Sending draft to your DM...
Done!
```

## TODO

- [ ] Socket Mode support: detect bot mentions in real time
- [ ] Register as a Slack bot and deploy to workspace
- [ ] Auto-trigger on mentions in specific channels and DMs
