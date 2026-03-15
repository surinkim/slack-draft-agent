# slack-draft-agent

슬랙에 올라오는 기술 문의 게시글 링크를 입력하면, 관련 컨텍스트를 자동으로 수집해서 답변 초안을 작성하고 본인 DM으로 전송해 주는 에이전트.

## 주요 기능

- 슬랙 게시글 + 스레드 전체 읽기
- 첨부 이미지 자동 분석 (Claude Vision)
- MCP 서버를 통한 컨텍스트 수집 (이전 답변 검색, 지표 조회, 코드/PR 확인 등)
- 답변 초안을 본인 DM으로 전송 (사람이 검토 후 직접 답변)

## 설치

```bash
git clone https://github.com/surinkim/slack-draft-agent.git
cd slack-draft-agent
pip install -r requirements.txt
```

## 설정

`.env.example`을 복사해서 `.env`를 만들고 값을 채워주세요.

```bash
cp .env.example .env
```

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Slack
SLACK_USER_TOKEN=xoxp-...        # User Token (스레드 읽기, 이미지 다운로드, DM 전송)
MY_SLACK_USER_ID=U...            # 초안을 받을 본인 유저 ID
```

### Slack User Token 필요 권한 (scopes)

- `channels:history` — 퍼블릭 채널 스레드 읽기
- `groups:history` — 프라이빗 채널 스레드 읽기
- `files:read` — 첨부 이미지 다운로드
- `im:write` — DM 채널 열기
- `chat:write` — DM 전송

## MCP 서버 추가

`.env`에 `MCP_SERVER_` 접두사로 환경변수를 추가하면 자동으로 연결됩니다.

```env
MCP_SERVER_SLACK=https://your-slack-mcp-server/sse
MCP_SERVER_GITHUB=https://your-github-mcp-server/sse
MCP_SERVER_FOO=https://your-custom-mcp-server/sse
```

키 이름에서 `MCP_SERVER_` 접두사를 제거하고 소문자로 변환한 값이 서버 이름으로 사용됩니다.
예: `MCP_SERVER_GITHUB` → 서버 이름 `github`

## 실행

```bash
# 인자로 전달
python agent.py "https://your-workspace.slack.com/archives/C01234567/p1234567890123456"

# 대화형 입력
python agent.py
Slack link: https://your-workspace.slack.com/archives/C01234567/p1234567890123456
```

### 출력 예시

```
Fetching thread: channel=C01234567, ts=1234567890.123456
Thread loaded: 523 chars, 1 image(s)
MCP servers: ['slack', 'github']
Calling Claude...

---
[초안]
(슬랙에 바로 붙여넣을 수 있는 답변)

[근거]
- 사용한 데이터 출처와 핵심 수치

[참고 링크]
- 관련 스레드 / PR / 문서 URL
---

Sending draft to your DM...
Done!
```

## TODO

- [ ] Socket Mode 지원: 봇 멘션 실시간 감지
- [ ] 슬랙 봇 등록 및 워크스페이스 배포
- [ ] 특정 채널 + DM에서 멘션 시 자동 동작
