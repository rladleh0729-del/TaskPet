# TaskPet 개인정보처리방침 / Privacy Policy

최종 수정: 2026-10-29 (프로그램 1.8.0·확장 1.3.0: 로봇에서 대화 보기·답 보내기)

이 문서는 Windows 프로그램 **TaskPet**과 브라우저 확장 **TaskPet for AI Chats**에 적용됩니다.

## 요약

TaskPet은 어떤 정보도 개발자나 다른 곳으로 **보내지 않습니다**. 모든 처리는 사용자의 컴퓨터 안에서만 일어납니다.

## 확장(TaskPet for AI Chats)이 다루는 정보

확장은 chatgpt.com, gemini.google.com, claude.ai, grok.com, kimi.ai(kimi.com)에서만 동작하며, 다음만 확인합니다.

- 입력창의 **'중지' 버튼(또는 중지 아이콘)이 있는지** — 답하는 중인지, 끝났는지 알기 위해
- 지금 보고 있는 **대화의 제목과 주소(URL)** — 로봇 말풍선에 이름을 보여 주고, 더블 클릭하면 그 탭으로 돌아가기 위해
- 브라우저 **탭 번호** — 같은 대화를 한 줄로 묶고, 탭이 닫히면 줄을 지우기 위해

**대화 글은 사용자가 로봇에서 그 탭 줄을 펼쳐 보는 동안에만 읽습니다.** 그동안 그 탭의 최근 메시지(최대 24개, 하나에 6,000자까지)를 읽어 로봇의 대화 기록창에 보여 주고, 카드를 닫으면 읽기를 멈추며 받아 둔 글 파일도 지웁니다. 로봇 입력칸에서 답을 보내면 그 글을 그 탭 입력창에 넣고 보내기 버튼을 누릅니다(사용자가 보냈을 때만, 그 탭 입력창에 쓰던 글이 있으면 보내지 않음).

위 정보는 모두 브라우저의 Native Messaging으로 같은 컴퓨터에 설치된 TaskPet 프로그램에만 전달되고, 인터넷으로 나가지 않습니다. 확장은 쿠키, 계정 정보, 방문 기록을 읽거나 저장하지 않습니다.

## Windows 프로그램(TaskPet)이 다루는 정보

- Claude Code: `~/.claude/settings.json`에 추가한 훅이 작업 시작·끝 신호를 설치 폴더(`%LOCALAPPDATA%\TaskPet`)의 파일에 적습니다.
- Codex: `~/.codex`의 기록 파일을 읽기만 합니다.
- Claude Code(터미널): 훅이 그 Claude Code 프로그램의 번호와 시작 시각을 함께 적습니다. 로봇에서 답을 보낼 때만 그 터미널 입력에 글을 넣고 Enter 를 누릅니다.
- ChatGPT 데스크톱 앱: Windows 화면 읽기 기능으로 왼쪽 목록의 "작업 중" 표시와 대화 제목을 확인합니다. 로봇에서 그 줄을 펼쳐 볼 때만 앱에 열려 있는 그 대화의 글을 읽고, 로봇에서 답을 보낼 때만 그 대화 입력창에 글을 넣어 보냅니다.

- Claude 데스크톱 앱: 같은 방식으로 왼쪽 목록의 "실행 중" 표시와 대화 제목만 확인합니다.

이 정보도 화면 표시에만 쓰이고, 설치 폴더 밖이나 인터넷으로 보내지 않습니다.

**새 버전 확인**: 프로그램은 켤 때와 10분마다 GitHub(`api.github.com`)에서 TaskPet 최신 릴리스 정보를 읽고, 사용자가 업데이트 줄을 더블 클릭하면 GitHub에서 새 설치 파일을 받습니다. 이때 사용자 정보는 보내지 않습니다(일반 웹 접속처럼 GitHub가 접속 주소를 볼 수는 있습니다).

## 제3자 제공·판매

없습니다. 광고, 분석 도구, 추적 코드도 없습니다.

## 삭제

TaskPet을 제거하면(로봇 우클릭 → TaskPet 제거, 또는 Windows 설정 → 앱) 설치 폴더와 추가했던 설정이 지워집니다. 확장은 브라우저 확장 페이지에서 삭제하면 됩니다.

## 문의

GitHub 이슈: https://github.com/rladleh0729-del/TaskPet/issues

---

## English

TaskPet (Windows app) and the TaskPet for AI Chats browser extension **do not send any data** to the developer or anyone else. Everything stays on your computer.

The extension runs only on chatgpt.com, gemini.google.com, claude.ai, grok.com and kimi.ai (kimi.com). It checks whether the input box shows a "Stop" button (to know if the AI is still answering), plus the current conversation's title, URL and tab id. **It reads message text only while you have that tab's row expanded in the robot** (the latest 24 messages, up to 6,000 characters each) to show them in the robot's chat view; it stops when you close the card, and the received text file is deleted. When you send a reply from the robot, it puts your text into that tab's message box and presses Send (only when you send it, and never over text you were already typing there). It never reads cookies, account data or browsing history. Everything is passed via Native Messaging to the TaskPet app on the same computer only.

The Windows app reads local Claude Code hook signals (including the Claude Code process id, used to type your reply into that terminal only when you send one), Codex session logs, and the ChatGPT / Claude desktop apps' "working" / "running" indicators via Windows UI Automation. For the ChatGPT desktop app it reads the open conversation's text only while you have that row expanded in the robot, and types your reply only when you send one. Every 10 minutes it reads the latest release info from GitHub (api.github.com) and, only when you double-click the update row, downloads the new installer from GitHub; no user data is sent. No data is sold or shared; there are no ads, analytics or trackers. Uninstalling removes the app folder and the settings it added.

Contact: https://github.com/rladleh0729-del/TaskPet/issues
