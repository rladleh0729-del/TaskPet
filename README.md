# TaskPet 🤖

AI 코딩 도구가 일하는 동안 화면 오른쪽 아래에서 상태를 알려 주는 작은 주황 로봇입니다.
**Claude Code**(데스크톱 앱·터미널·VS Code), **Claude 데스크톱 앱 일반 채팅**, **Codex**(ChatGPT 데스크톱 앱·Codex CLI), **ChatGPT 일반 채팅**(데스크톱 앱, 그리고 확장을 넣으면 브라우저의 chatgpt.com)를 지원하고, 확장을 넣으면 브라우저의 **Gemini**·**Claude 웹**(claude.ai)·**Grok**·**Kimi**도 보입니다. Windows 10/11 전용입니다.
줄마다 붙는 알약 모양 이름표로 구분됩니다: **Claude**·**Claude 채팅**·**Claude 웹**은 주황, **ChatGPT**는 청록, **Codex**는 파랑, **Gemini**는 보라, **Grok**은 회색, **Kimi**는 청록.

| 상태 | 로봇 | 말풍선 |
|---|---|---|
| 일하는 중 | 팔을 흔들고, 안테나·가슴이 노랑, 머리 옆에 작업 개수 | 대화 제목 · 진행 1분 |
| **내 승인·답변을 기다리는 중** | 동그란 눈, 안테나·가슴이 빨강, 머리 옆 ! 배지, 경고음 | ● 대화 제목 · 응답 대기 2분 |
| 끝남 | ^^ 웃는 눈, 안테나·가슴이 초록, 머리 옆 초록 ✓ 배지, 짧은 소리 | ✓ 초록 대화 제목 · 완료 · 3분 전 |

"작업을 맡겨 놓고 다른 일을 하다 보니, 사실은 권한 승인을 기다리며 멈춰 있었다"를 막는 것이 목적입니다.

## 설치

1. [Releases](../../releases)에서 `TaskPet.exe`를 내려받습니다.
2. 실행하면 바로 설치되고 로봇이 나타납니다. 컴퓨터를 켤 때도 자동으로 실행됩니다.
   받은 `TaskPet.exe`는 설치 파일입니다 — 프로그램을 `%LOCALAPPDATA%\TaskPet` 폴더에 한 번 풀어 두므로, 설치된 로봇은 켤 때마다 풀 필요 없이 바로(1초 안에) 뜹니다. 예전 버전이 임시 폴더에 남긴 `_MEI…` 폴더도 로봇이 정리합니다.
3. 이미 열려 있던 Claude Code 세션은 새로 시작해야 잡힙니다.
4. 로봇 화면 글은 Windows 언어에 맞춰 나옵니다(한국어·English·日本語·简体中文·繁體中文·Español·Português·Français·Deutsch·Русский). 바꾸려면 우클릭 → **설정 → 언어 · Language**.

### 브라우저 ChatGPT·Gemini·Claude·Grok·Kimi도 보려면 (선택)

Chrome·Brave·Edge에서 쓸 수 있습니다.

1. **[Chrome 웹 스토어의 TaskPet for AI Chats](https://chromewebstore.google.com/detail/ojhigjdohhpkdkolpeeobffggkejpakn)** 에서 **Chrome에 추가**를 누릅니다. (로봇 우클릭 → **브라우저 확장 설치**를 눌러도 이 페이지가 열립니다)
2. **브라우저를 완전히 껐다가 다시 켭니다**(TaskPet 설치 때 등록한 연결 정보를 브라우저가 다시 읽어야 합니다).

chatgpt.com·gemini.google.com·claude.ai·grok.com·kimi.ai에서 질문을 보내면 "ChatGPT 웹"·"Gemini"·"Claude 웹"·"Grok"·"Kimi" 줄이 생기고, 더블 클릭하면 그 탭으로 이동합니다.
Chrome·Brave·Edge가 있는데 확장이 없으면 로봇에 초록 **"브라우저 AI 채팅도 보려면 확장 설치"** 줄이 한 번 뜹니다(더블 클릭 = 스토어 열기, ✕ = 다시 안 뜸). 확장을 처음 설치하면 TaskPet 받는 페이지가 새 탭으로 열립니다.
예전에 개발자 모드로 직접 불러온 확장을 쓰고 있었다면, 스토어판을 설치한 뒤 예전 것은 확장 페이지에서 지워 주세요(같은 일을 하는 확장이라 하나면 됩니다). 스토어판은 자동으로 업데이트됩니다.

> 서명되지 않은 프로그램이라 Windows가 "PC 보호" 경고를 띄울 수 있습니다. **추가 정보 → 실행**을 누르세요. 소스 코드는 이 저장소에 전부 공개되어 있습니다.

## 사용법

- **로봇 클릭**: 말풍선 숨기기/보이기
- **로봇 드래그**: 위치 옮기기 (옮긴 자리를 기억해서 다시 켜도 그 자리에 나타납니다)
- **말풍선 줄 한 번 클릭**(또는 **›**): 그 줄만 펼친 카드로 보기(더블 클릭인지 0.4초 기다린 뒤). **더블 클릭**: 펼치지 않고 그 대화를 Claude 앱 / ChatGPT 앱 / 브라우저 탭에서 바로 열기 (마우스를 올린 줄은 제목 색이 바뀝니다)
- **펼친 카드 = 채팅**: Claude Code 대화를 채팅처럼 보여 줍니다 — 내가 보낸 메시지(오른쪽 주황), Claude의 글(왼쪽 흰 칸, 소제목·목록 정리), 그 사이에 도구를 쓴 기록 한 줄(예: `읽음 taskpet.py · 편집함 2개 · 명령 실행 3개`), 그리고 맨 아래에 계획(✓ 끝남 · ● 하는 중 · ○ 남음)과 지금 하는 일(예: `● 읽는 중 taskpet.py  3분 12초`, 없으면 `생각 중…`). 일하는 중에는 1초마다 그 자리에서 늘어나고, 입력칸에 쓰던 글은 끊기지 않습니다. 최근 대화 6개부터 보이고, **맨 위에서 휠을 더 올리면 이전 대화를 6개씩 더 불러옵니다**(읽던 자리는 그대로). Claude가 일하는 중에 끼워 보낸 메시지도 내 메시지로 보이고, 대화 속 그림(내가 붙인 것·Claude가 읽은 것)은 작게 보입니다(누르면 크게). 다른 프로그램을 눌러도 카드는 닫히지 않고, **‹ 목록**·✕·Esc로 목록으로 돌아갑니다
- **보낼 글 입력칸**: Claude 앱 입력창처럼 폭 가득한 여러 줄 칸(6줄까지 늘어남), Enter = 보내기, Shift+Enter = 줄바꿈, 글씨는 Claude 글과 같은 글씨체. 한글을 조합하는 중인 글자도 같은 크기로 보입니다. 쓰던 글은 세션마다 저장돼 카드를 닫거나 로봇을 다시 켜도 남고(목록 줄에 ✎), 쓰는 동안에는 카드가 다시 그려지지 않아 글자가 끊기지 않습니다
- **웹·ChatGPT 앱·터미널에서도 대화 보기·답 보내기**: 브라우저 AI 탭(확장 1.3 이상), ChatGPT 데스크톱 앱, 터미널의 Claude Code도 줄을 펼쳐 대화를 보고 입력칸에서 바로 보낼 수 있습니다. 그 탭·대화에 쓰던 글이 있으면 보내지 않습니다.
  - **브라우저 AI 탭**: 펼쳐 보는 동안만 그 탭의 최근 메시지 24개를 읽어 보여 주고, 보낸 글은 그 탭 입력창에 넣어 보내기를 누릅니다. AI가 답하는 중에는 보낼 수 없습니다.
  - **ChatGPT 앱**: 앱에 그 대화가 열려 있을 때 글이 보입니다. 보낼 때 다른 대화를 보고 있었다면 잠깐 바꿔서 보낸 뒤 원래 대화로 돌려놓습니다.
  - **터미널**: 그 터미널의 입력에 글을 넣고 Enter를 누릅니다(여러 줄은 한 줄로 이어짐). 권한 확인이나 질문 카드처럼 선택 메뉴로 멈춘 때는 터미널에서 직접 골라 주세요. 줄을 더블 클릭하면 그 터미널 창이 앞으로 옵니다.
  - 이미지 첨부는 아직 Claude 데스크톱 앱 세션만 됩니다.
- **켜자마자 최근 대화**: 컴퓨터를 다시 켜서 로봇이 시작되면 가장 최근 Claude Code 대화 1개가 줄로 떠 있어, 바로 펼쳐 보고 이어서 보낼 수 있습니다(✕로 지우면 새 일이 생길 때까지 다시 안 뜸)
- **✕**: 그 줄 지우기
- **선택지 질문에 바로 답하기**: Claude 데스크톱 앱의 Claude Code가 선택지 질문(질문 카드 포함)으로 멈추면, 그 줄 앞에 빨간 ●가 붙고 ›로 펼치면 질문과 선택지 버튼이 나옵니다. 버튼을 누르거나 입력칸에 직접 써서 보내면, Claude 앱을 앞으로 가져오지 않고 그 세션에 답이 들어갑니다. (Claude 앱이 최소화돼 있어도 화면에 아무것도 띄우지 않고 처리합니다) (다른 세션을 보고 있었다면 잠깐 바꿔서 보낸 뒤 원래 화면으로 돌려놓고, 그 세션 입력창에 쓰던 글이 있으면 보내지 않습니다)
- **끝난 답변 보기·보내기**: Claude Code가 답을 끝내면 ›로 펼쳐서 마지막 답변을 볼 수 있습니다(데스크톱 앱·터미널·VS Code 모두). Claude 데스크톱 앱과 VS Code의 Claude Code 세션은 펼친 카드의 입력칸에 써서 ➤로 로봇에서 언제든 글을 보낼 수 있습니다. 답하는 중에 보내면 앱이 대기열에 넣었다가 이어서 읽습니다. 질문 카드에도 답할 수 있습니다(창을 앞으로 가져오지 않음. VS Code는 Claude 패널에 그 세션이 열려 있어야 함).
  Claude 데스크톱 앱 세션은 입력칸에서 **Ctrl+V**로 스크린샷을 붙이거나 **이미지** 버튼으로 이미지 파일을 고르면, 보낼 때 그 세션 입력창에 이미지가 진짜 첨부됩니다. 붙여넣는 1~2초 동안만 그 창에 키보드 포커스가 가고(창은 투명해서 안 보임), 끝나면 쓰던 창으로 포커스와 클립보드 내용이 돌아옵니다. 붙인 이미지는 `사진\TaskPet` 폴더에 저장됩니다.
- **새 버전 알림**: 10분마다 새 버전을 확인해, 있으면 초록 "⬆ 새 버전" 줄이 생깁니다. 더블 클릭하면 받아서 업데이트합니다.
- **우클릭**: 버전 보기 · 완료 기록 지우기 · 설정 · 브라우저 확장 설치(웹 스토어) · 제거 · 종료
- **설정**(우클릭 → 설정):
  - **말풍선 자동 숨기기**: 안 함 / 10초 / 30초 / 1분 뒤. 새 알림이 오면 다시 나타나고, 말풍선 위에 마우스를 올려 두거나 보낼 글을 쓰는 동안은 숨기지 않습니다.
  - **화면에 보이는 세션은 알리지 않기**(기본 켬): 창이 화면에 보이면(맨 앞이 아니어도, 나란히 띄워 둔 경우 포함) 그 줄을 숨기고 소리도 내지 않습니다. VS Code는 Claude Code 세션 줄 모두, Claude 앱과 ChatGPT 앱(일반 채팅·Codex)은 지금 띄워 둔 그 대화 줄만.
  - **끝난 답변 미리보기**(기본 켬) · **소리 끄기**
  - **언어 · Language**: 자동(Windows 설정) 또는 10개 언어 중 하나. 고르면 로봇이 그 언어로 다시 켜집니다.
- 줄 맨 앞의 작은 아이콘으로 어느 AI인지 구분됩니다 (Claude 주황 빛살, GPT 매듭, Gemini 별, Grok 사선, Kimi K). 각 회사를 떠올리게 직접 그린 모양이며, 공식 로고 파일이 아닙니다.

## 제거

로봇 우클릭 → **TaskPet 제거**, 또는 Windows **설정 → 앱 → 설치된 앱 → TaskPet → 제거**.
Claude Code 설정에 넣었던 훅, 자동 실행, 설치 폴더가 모두 지워지고 다른 설정은 그대로 남습니다.

## 작동 방식

- **Claude Code**: `~/.claude/settings.json`에 훅 5개(UserPromptSubmit, Stop, Notification, PostToolUse, SessionEnd)를 **추가만** 합니다. 기존 설정은 처음 설치할 때 `settings.json.taskpet-backup`으로 백업됩니다. 훅은 작은 프로그램(`taskpet-hook.exe`)이 신호를 파일에 적기만 하고 바로 끝납니다. VS Code의 Claude 확장도 안에서 Claude Code를 쓰므로 똑같이 잡힙니다.
- **터미널의 Claude Code**: 훅이 자기를 부른 Claude Code 프로그램의 번호와 시작 시각도 함께 적습니다. 로봇에서 답을 보낼 때만 작은 프로그램(`taskpet-term.exe`)이 그 터미널 입력에 글자를 넣습니다. 번호를 다른 프로그램이 다시 쓰는 경우에 대비해 시작 시각이 맞을 때만 넣습니다.
- **Codex**: 설정을 바꾸지 않고 `~/.codex/sessions`의 기록 파일을 읽기만 합니다. Codex는 현재 시작·완료만 표시하고, 승인 대기는 표시하지 않습니다.
- **ChatGPT 일반 채팅**: 일반 채팅은 컴퓨터에 기록이 남지 않아서, 작은 프로그램(`taskpet-chatgpt.exe`)이 2초마다 ChatGPT 데스크톱 앱 창을 Windows 화면 읽기 기능(UI Automation)으로 읽습니다. 목록 줄의 "작업 중" 표시, 또는 지금 열린 대화의 보내기 버튼이 '답변 중지'로 바뀐 것으로 답하는 중인지 압니다(그래서 앱에서 다른 대화를 보는 동안 답하는 대화는 놓칠 수 있습니다). 대화 글은 로봇에서 그 줄을 펼쳐 보는 동안에만 읽고, 로봇에서 보낼 때만 입력창에 글을 넣습니다. ChatGPT 창이 열려 있어야 합니다.
- **Claude 데스크톱 앱 일반 채팅**: 같은 프로그램이 Claude 앱 창도 읽어 왼쪽 목록에서 **"실행 중" 표시가 붙은 대화 제목**만 확인합니다. 채팅 화면이 보일 때만 판단하고, Code 탭에 있는 동안에는 상태를 그대로 둡니다.
- **새 버전 확인**: 켤 때와 10분마다 GitHub의 최신 릴리스 정보(`api.github.com`)만 읽습니다. 내 정보는 보내지 않습니다.
- **브라우저 AI 채팅**: 확장(`extension/`)이 chatgpt.com·gemini.google.com·claude.ai·grok.com·kimi.ai 페이지에서 입력창의 **'중지' 버튼이 있는지**로 답하는 중/끝남을 알아냅니다. 그 상태(대화 제목·주소)는 브라우저의 Native Messaging으로 내 컴퓨터의 작은 프로그램(`taskpet-native.exe`)에 넘겨지고, 그 프로그램이 로봇에게 전달합니다. **대화 글은 로봇에서 그 탭 줄을 펼쳐 보는 동안에만** 읽어 설치 폴더의 임시 파일(`web-chat`)로 넘기고, 카드를 닫으면 멈추고 그 파일도 지웁니다.
- 모든 정보는 내 컴퓨터 안에서만 읽고, 어디에도 보내지 않습니다. (인터넷 연결은 새 버전 확인·받기뿐입니다)
- "대화 바로 열기"는 각 앱의 공개되지 않은 링크 형식을 사용하므로, 앱 업데이트 후 동작하지 않을 수 있습니다. 그때는 가장 최근 대화가 열립니다.

## 직접 빌드

```
pip install pillow pyinstaller
python build.py
```

`dist\TaskPet.exe`(설치 파일)가 만들어집니다. 로봇은 PyInstaller 폴더판으로 만들고, 그 폴더를 zip으로 묶어 작은 C# 설치 프로그램(`src\setup.cs`) 안에 넣습니다. 훅, ChatGPT·Claude 앱 감시(COM UI Automation), Native Messaging 연결 프로그램, 터미널 도우미, 설치 프로그램은 Windows에 기본으로 있는 C# 컴파일러(.NET Framework 4)로 빌드합니다.
창 없는 프로그램이라 오류가 나면 설치 폴더(`%LOCALAPPDATA%\TaskPet`)의 `error.log`에 기록됩니다.

---

## English

TaskPet is a tiny orange pixel robot that sits at the bottom right of your screen and shows what your AI coding agents are doing: **working**, **waiting for your approval** (red, with a sound), or **done** (green, with a short chime). It supports **Claude Code** (desktop app, terminal and VS Code), **regular chats in the Claude desktop app**, **Codex** (ChatGPT desktop app / Codex CLI) and **regular ChatGPT chats** in the desktop app, on Windows 10/11. Claude rows are labeled in orange, Codex and ChatGPT rows in blue. When Claude Code in the Claude desktop app stops with a multiple-choice question, the question and its choices appear under the row — click one (or type under "Other") to answer that session without bringing the app to the front. Hover a row to highlight it; a green "new version" row appears when an update is available — double-click it to update.

- Download `TaskPet.exe` from Releases and run it. It is a small installer: it unpacks TaskPet once into `%LOCALAPPDATA%\TaskPet` and starts with Windows, so the installed robot starts in well under a second.
- The robot speaks 10 languages (Korean, English, Japanese, Simplified/Traditional Chinese, Spanish, Portuguese, French, German, Russian) and follows your Windows language. Change it from right-click → **Settings → Language**; the robot restarts in that language.
- Click the robot to hide/show the bubble, drag it to move (the position is remembered), mute sounds from the right-click menu, small hand-drawn icons (not official logos) show which AI each row is from, double-click a row to jump to that chat, right-click for the menu.
- Expand a row to read the chat and reply from the robot. This now also works for browser AI tabs (extension 1.3+), the ChatGPT desktop app and Claude Code in a terminal. Browser tabs: the latest 24 messages are read only while the row is expanded, and your reply is typed into that tab. ChatGPT app: the chat must be open in the app to be shown; sending may briefly switch to that chat and then switches back. Terminal: your reply is typed into that terminal's input (multiple lines are joined); permission prompts and question cards must be answered in the terminal itself. Nothing is sent over a tab or chat where you were already typing.
- Uninstall from the right-click menu or Windows Settings → Apps. All hooks it added are removed; your other settings stay untouched.
- Claude Code is tracked through hooks it appends to `~/.claude/settings.json` (backed up first). Codex is tracked by reading `~/.codex/sessions` only. Regular ChatGPT chats leave no local record, so a small helper reads the ChatGPT window through Windows UI Automation every 2 seconds and looks for the "working" indicator next to chat titles or the "Stop" button of the open chat (the ChatGPT window must be open); it reads the open chat's text only while you expand its row; the same helper reads the Claude desktop app's sidebar for the "running" indicator while its chat view is shown. Nothing leaves your computer; the only network access is a check of the latest GitHub release every 10 minutes.
- Optional, for chatgpt.com, gemini.google.com, claude.ai, grok.com and kimi.ai in Chrome/Brave/Edge: install **[TaskPet for AI Chats from the Chrome Web Store](https://chromewebstore.google.com/detail/ojhigjdohhpkdkolpeeobffggkejpakn)** (right-click the robot → **Install browser extension (Web Store)** opens the same page; the extension is also translated into 10 languages), then fully restart the browser. The extension only checks whether the "Stop" button is present and passes the state (title, URL) to TaskPet through Native Messaging (`taskpet-native.exe`). It reads message text only while you expand that tab's row in the robot, and stops when you close it.

Not affiliated with Anthropic or OpenAI. "Claude", "Codex" and "ChatGPT" are trademarks of their respective owners.

## License

MIT
