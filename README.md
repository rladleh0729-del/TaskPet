# TaskPet 🤖

AI 코딩 도구가 일하는 동안 화면 오른쪽 아래에서 상태를 알려 주는 작은 주황 로봇입니다.
**Claude Code**, **Codex**(ChatGPT 데스크톱 앱·Codex CLI), **ChatGPT 일반 채팅**(데스크톱 앱)을 지원합니다. Windows 10/11 전용입니다.
줄마다 붙는 이름표로 구분됩니다: **Claude**는 주황, **Codex**·**ChatGPT**는 파랑.

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

> 서명되지 않은 프로그램이라 Windows가 "PC 보호" 경고를 띄울 수 있습니다. **추가 정보 → 실행**을 누르세요. 소스 코드는 이 저장소에 전부 공개되어 있습니다.

## 사용법

- **로봇 클릭**: 말풍선 숨기기/보이기
- **로봇 드래그**: 위치 옮기기
- **말풍선 줄 더블 클릭**: 그 대화를 Claude 앱 / ChatGPT 앱에서 바로 열기
- **✕**: 그 줄 지우기
- **우클릭**: 완료 기록 지우기 · 제거 · 종료

## 제거

로봇 우클릭 → **TaskPet 제거**, 또는 Windows **설정 → 앱 → 설치된 앱 → TaskPet → 제거**.
Claude Code 설정에 넣었던 훅, 자동 실행, 설치 폴더가 모두 지워지고 다른 설정은 그대로 남습니다.

## 작동 방식

- **Claude Code**: `~/.claude/settings.json`에 훅 5개(UserPromptSubmit, Stop, Notification, PostToolUse, SessionEnd)를 **추가만** 합니다. 기존 설정은 처음 설치할 때 `settings.json.taskpet-backup`으로 백업됩니다. 훅은 작은 프로그램(`taskpet-hook.exe`)이 신호를 파일에 적기만 하고 바로 끝납니다.
- **Codex**: 설정을 바꾸지 않고 `~/.codex/sessions`의 기록 파일을 읽기만 합니다. Codex는 현재 시작·완료만 표시하고, 승인 대기는 표시하지 않습니다.
- **ChatGPT 일반 채팅**: 일반 채팅은 컴퓨터에 기록이 남지 않아서, 작은 프로그램(`taskpet-chatgpt.exe`)이 2초마다 ChatGPT 데스크톱 앱 창을 Windows 화면 읽기 기능(UI Automation)으로 읽어 왼쪽 목록에서 **"작업 중" 표시가 붙은 대화 제목**만 확인합니다. 대화 내용은 읽지 않고, 창을 누르지도 않습니다(더블 클릭으로 대화를 열 때만 그 줄을 누릅니다). ChatGPT 창이 열려 있어야 하며, 시작·완료만 표시합니다.
- 모든 정보는 내 컴퓨터 안에서만 읽고, 어디에도 보내지 않습니다.
- "대화 바로 열기"는 각 앱의 공개되지 않은 링크 형식을 사용하므로, 앱 업데이트 후 동작하지 않을 수 있습니다. 그때는 가장 최근 대화가 열립니다.

## 직접 빌드

```
pip install pillow pyinstaller
python build.py
```

`dist\TaskPet.exe`가 만들어집니다. 훅과 ChatGPT 감시 프로그램은 Windows에 기본으로 있는 C# 컴파일러(.NET Framework 4)로 빌드합니다.
창 없는 프로그램이라 오류가 나면 설치 폴더(`%LOCALAPPDATA%\TaskPet`)의 `error.log`에 기록됩니다.

---

## English

TaskPet is a tiny orange pixel robot that sits at the bottom right of your screen and shows what your AI coding agents are doing: **working**, **waiting for your approval** (red, with a sound), or **done** (green, with a short chime). It supports **Claude Code**, **Codex** (ChatGPT desktop app / Codex CLI) and **regular ChatGPT chats** in the desktop app, on Windows 10/11. Claude rows are labeled in orange, Codex and ChatGPT rows in blue.

- Download `TaskPet.exe` from Releases and run it. It installs itself and starts with Windows.
- Click the robot to hide/show the bubble, drag it to move, double-click a row to jump to that chat, right-click for the menu.
- Uninstall from the right-click menu or Windows Settings → Apps. All hooks it added are removed; your other settings stay untouched.
- Claude Code is tracked through hooks it appends to `~/.claude/settings.json` (backed up first). Codex is tracked by reading `~/.codex/sessions` only. Regular ChatGPT chats leave no local record, so a small helper reads the ChatGPT window through Windows UI Automation every 2 seconds and only looks for the "working" indicator next to chat titles in the sidebar (the ChatGPT window must be open). Nothing leaves your computer.

Not affiliated with Anthropic or OpenAI. "Claude", "Codex" and "ChatGPT" are trademarks of their respective owners.

## License

MIT
