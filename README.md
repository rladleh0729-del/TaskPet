# TaskPet 🤖

AI 코딩 도구가 일하는 동안 화면 오른쪽 아래에서 상태를 알려 주는 작은 주황 로봇입니다.
**Claude Code**(데스크톱 앱·터미널·VS Code), **Claude 데스크톱 앱 일반 채팅**, **Codex**(ChatGPT 데스크톱 앱·Codex CLI), **ChatGPT 일반 채팅**(데스크톱 앱, 그리고 확장을 넣으면 브라우저의 chatgpt.com)를 지원하고, 확장을 넣으면 브라우저의 **Gemini**·**Claude 웹**(claude.ai)·**Grok**·**Kimi**도 보입니다. Windows 10/11 전용입니다.
줄마다 붙는 이름표로 구분됩니다: **Claude**·**Claude 채팅**·**Claude 웹**은 주황, **Codex**·**ChatGPT**는 파랑, **Gemini**는 보라, **Grok**은 은색, **Kimi**는 청록.

| 상태 | 로봇 | 말풍선 |
|---|---|---|
| 일하는 중 | 팔을 흔들고, 머리 위에 작업 개수 | ⚙ 대화 제목 · 1분 20초 진행 중 |
| **내 승인·답변을 기다리는 중** | 눈과 배지가 빨개지고 경고음 | ❗ 대화 제목 · 응답 대기 2분째 |
| 끝남 | 초록 눈, ✓ 배지, 짧은 소리 | ✅ 대화 제목 · 완료 22:30 · 4분 |

"작업을 맡겨 놓고 다른 일을 하다 보니, 사실은 권한 승인을 기다리며 멈춰 있었다"를 막는 것이 목적입니다.

## 설치

1. [Releases](../../releases)에서 `TaskPet.exe`를 내려받습니다.
2. 실행하면 바로 설치되고 로봇이 나타납니다. 컴퓨터를 켤 때도 자동으로 실행됩니다.
3. 이미 열려 있던 Claude Code 세션은 새로 시작해야 잡힙니다.

### 브라우저 ChatGPT·Gemini·Claude·Grok·Kimi도 보려면 (선택)

Chrome·Brave·Edge에서 쓸 수 있습니다.

1. **[Chrome 웹 스토어의 TaskPet for AI Chats](https://chromewebstore.google.com/detail/ojhigjdohhpkdkolpeeobffggkejpakn)** 에서 **Chrome에 추가**를 누릅니다. (로봇 우클릭 → **브라우저 확장 설치**를 눌러도 이 페이지가 열립니다)
2. **브라우저를 완전히 껐다가 다시 켭니다**(TaskPet 설치 때 등록한 연결 정보를 브라우저가 다시 읽어야 합니다).

chatgpt.com·gemini.google.com·claude.ai·grok.com·kimi.ai에서 질문을 보내면 "ChatGPT 웹"·"Gemini"·"Claude 웹"·"Grok"·"Kimi" 줄이 생기고, 더블 클릭하면 그 탭으로 이동합니다.
예전에 개발자 모드로 직접 불러온 확장을 쓰고 있었다면, 스토어판을 설치한 뒤 예전 것은 확장 페이지에서 지워 주세요(같은 일을 하는 확장이라 하나면 됩니다). 스토어판은 자동으로 업데이트됩니다.

> 서명되지 않은 프로그램이라 Windows가 "PC 보호" 경고를 띄울 수 있습니다. **추가 정보 → 실행**을 누르세요. 소스 코드는 이 저장소에 전부 공개되어 있습니다.

## 사용법

- **로봇 클릭**: 말풍선 숨기기/보이기
- **로봇 드래그**: 위치 옮기기 (옮긴 자리를 기억해서 다시 켜도 그 자리에 나타납니다)
- **말풍선 줄 더블 클릭**: 그 대화를 Claude 앱 / ChatGPT 앱 / 브라우저 탭에서 바로 열기 (마우스를 올린 줄은 배경이 밝아집니다)
- **✕**: 그 줄 지우기
- **선택지 질문에 바로 답하기**: Claude 데스크톱 앱의 Claude Code가 선택지 질문(질문 카드 포함)으로 멈추면, 그 줄 아래에 질문과 선택지 버튼이 나옵니다. 버튼을 누르거나 **기타**에 직접 써서 보내면, Claude 앱을 앞으로 가져오지 않고 그 세션에 답이 들어갑니다. (Claude 앱이 최소화돼 있어도 화면에 아무것도 띄우지 않고 처리합니다) (다른 세션을 보고 있었다면 잠깐 바꿔서 보낸 뒤 원래 화면으로 돌려놓고, 그 세션 입력창에 쓰던 글이 있으면 보내지 않습니다)
- **새 버전 알림**: 10분마다 새 버전을 확인해, 있으면 초록 "⬆ 새 버전" 줄이 생깁니다. 더블 클릭하면 받아서 업데이트합니다.
- **우클릭**: 버전 보기 · 완료 기록 지우기 · 소리 끄기/켜기 · 브라우저 확장 설치(웹 스토어) · 제거 · 종료
- 줄 맨 앞의 작은 아이콘으로 어느 AI인지 구분됩니다 (Claude 주황 빛살, GPT 매듭, Gemini 별, Grok 사선, Kimi K). 각 회사를 떠올리게 직접 그린 모양이며, 공식 로고 파일이 아닙니다.

## 제거

로봇 우클릭 → **TaskPet 제거**, 또는 Windows **설정 → 앱 → 설치된 앱 → TaskPet → 제거**.
Claude Code 설정에 넣었던 훅, 자동 실행, 설치 폴더가 모두 지워지고 다른 설정은 그대로 남습니다.

## 작동 방식

- **Claude Code**: `~/.claude/settings.json`에 훅 5개(UserPromptSubmit, Stop, Notification, PostToolUse, SessionEnd)를 **추가만** 합니다. 기존 설정은 처음 설치할 때 `settings.json.taskpet-backup`으로 백업됩니다. 훅은 작은 프로그램(`taskpet-hook.exe`)이 신호를 파일에 적기만 하고 바로 끝납니다. VS Code의 Claude 확장도 안에서 Claude Code를 쓰므로 똑같이 잡힙니다.
- **Codex**: 설정을 바꾸지 않고 `~/.codex/sessions`의 기록 파일을 읽기만 합니다. Codex는 현재 시작·완료만 표시하고, 승인 대기는 표시하지 않습니다.
- **ChatGPT 일반 채팅**: 일반 채팅은 컴퓨터에 기록이 남지 않아서, 작은 프로그램(`taskpet-chatgpt.exe`)이 2초마다 ChatGPT 데스크톱 앱 창을 Windows 화면 읽기 기능(UI Automation)으로 읽어 왼쪽 목록에서 **"작업 중" 표시가 붙은 대화 제목**만 확인합니다. 대화 내용은 읽지 않고, 창을 누르지도 않습니다(더블 클릭으로 대화를 열 때만 그 줄을 누릅니다). ChatGPT 창이 열려 있어야 하며, 시작·완료만 표시합니다.
- **Claude 데스크톱 앱 일반 채팅**: 같은 프로그램이 Claude 앱 창도 읽어 왼쪽 목록에서 **"실행 중" 표시가 붙은 대화 제목**만 확인합니다. 채팅 화면이 보일 때만 판단하고, Code 탭에 있는 동안에는 상태를 그대로 둡니다.
- **새 버전 확인**: 켤 때와 10분마다 GitHub의 최신 릴리스 정보(`api.github.com`)만 읽습니다. 내 정보는 보내지 않습니다.
- **브라우저 AI 채팅**: 확장(`extension/`)이 chatgpt.com·gemini.google.com·claude.ai·grok.com·kimi.ai 페이지에서 입력창의 **'중지' 버튼이 있는지만** 확인해 답하는 중/끝남을 알아냅니다. 알아낸 상태(대화 제목·주소)는 브라우저의 Native Messaging으로 내 컴퓨터의 작은 프로그램(`taskpet-native.exe`)에 넘겨지고, 그 프로그램이 로봇에게 전달합니다. 대화 내용은 읽지 않습니다.
- 모든 정보는 내 컴퓨터 안에서만 읽고, 어디에도 보내지 않습니다. (인터넷 연결은 새 버전 확인·받기뿐입니다)
- "대화 바로 열기"는 각 앱의 공개되지 않은 링크 형식을 사용하므로, 앱 업데이트 후 동작하지 않을 수 있습니다. 그때는 가장 최근 대화가 열립니다.

## 직접 빌드

```
pip install pillow pyinstaller
python build.py
```

`dist\TaskPet.exe`가 만들어집니다. 훅, ChatGPT·Claude 앱 감시, Native Messaging 연결 프로그램은 Windows에 기본으로 있는 C# 컴파일러(.NET Framework 4)로 빌드합니다.
창 없는 프로그램이라 오류가 나면 설치 폴더(`%LOCALAPPDATA%\TaskPet`)의 `error.log`에 기록됩니다.

---

## English

TaskPet is a tiny orange pixel robot that sits at the bottom right of your screen and shows what your AI coding agents are doing: **working**, **waiting for your approval** (red, with a sound), or **done** (green, with a short chime). It supports **Claude Code** (desktop app, terminal and VS Code), **regular chats in the Claude desktop app**, **Codex** (ChatGPT desktop app / Codex CLI) and **regular ChatGPT chats** in the desktop app, on Windows 10/11. Claude rows are labeled in orange, Codex and ChatGPT rows in blue. When Claude Code in the Claude desktop app stops with a multiple-choice question, the question and its choices appear under the row — click one (or type under "Other") to answer that session without bringing the app to the front. Hover a row to highlight it; a green "new version" row appears when an update is available — double-click it to update.

- Download `TaskPet.exe` from Releases and run it. It installs itself and starts with Windows.
- Click the robot to hide/show the bubble, drag it to move (the position is remembered), mute sounds from the right-click menu, small hand-drawn icons (not official logos) show which AI each row is from, double-click a row to jump to that chat, right-click for the menu.
- Uninstall from the right-click menu or Windows Settings → Apps. All hooks it added are removed; your other settings stay untouched.
- Claude Code is tracked through hooks it appends to `~/.claude/settings.json` (backed up first). Codex is tracked by reading `~/.codex/sessions` only. Regular ChatGPT chats leave no local record, so a small helper reads the ChatGPT window through Windows UI Automation every 2 seconds and only looks for the "working" indicator next to chat titles in the sidebar (the ChatGPT window must be open); the same helper reads the Claude desktop app's sidebar for the "running" indicator while its chat view is shown. Nothing leaves your computer; the only network access is a check of the latest GitHub release every 10 minutes.
- Optional, for chatgpt.com, gemini.google.com, claude.ai, grok.com and kimi.ai in Chrome/Brave/Edge: install **[TaskPet for AI Chats from the Chrome Web Store](https://chromewebstore.google.com/detail/ojhigjdohhpkdkolpeeobffggkejpakn)** (right-click the robot → **브라우저 확장 설치** opens the same page), then fully restart the browser. The extension only checks whether the "Stop" button is present and passes the state (title, URL) to TaskPet through Native Messaging (`taskpet-native.exe`). It never reads message content.

Not affiliated with Anthropic or OpenAI. "Claude", "Codex" and "ChatGPT" are trademarks of their respective owners.

## License

MIT
