# TaskPet 개인정보처리방침 / Privacy Policy

최종 수정: 2026-10-24

이 문서는 Windows 프로그램 **TaskPet**과 브라우저 확장 **TaskPet for AI Chats**에 적용됩니다.

## 요약

TaskPet은 어떤 정보도 개발자나 다른 곳으로 **보내지 않습니다**. 모든 처리는 사용자의 컴퓨터 안에서만 일어납니다.

## 확장(TaskPet for AI Chats)이 다루는 정보

확장은 chatgpt.com, gemini.google.com, claude.ai, grok.com, kimi.ai(kimi.com)에서만 동작하며, 다음만 확인합니다.

- 입력창의 **'중지' 버튼(또는 중지 아이콘)이 있는지** — 답하는 중인지, 끝났는지 알기 위해
- 지금 보고 있는 **대화의 제목과 주소(URL)** — 로봇 말풍선에 이름을 보여 주고, 더블 클릭하면 그 탭으로 돌아가기 위해
- 브라우저 **탭 번호** — 같은 대화를 한 줄로 묶고, 탭이 닫히면 줄을 지우기 위해

**대화 내용(질문·답변)은 읽지 않습니다.** 위 정보는 브라우저의 Native Messaging으로 같은 컴퓨터에 설치된 TaskPet 프로그램에만 전달되고, 인터넷으로 나가지 않습니다. 확장은 쿠키, 계정 정보, 입력 내용, 방문 기록을 읽거나 저장하지 않습니다.

## Windows 프로그램(TaskPet)이 다루는 정보

- Claude Code: `~/.claude/settings.json`에 추가한 훅이 작업 시작·끝 신호를 설치 폴더(`%LOCALAPPDATA%\TaskPet`)의 파일에 적습니다.
- Codex: `~/.codex`의 기록 파일을 읽기만 합니다.
- ChatGPT 데스크톱 앱: Windows 화면 읽기 기능으로 왼쪽 목록의 "작업 중" 표시와 대화 제목만 확인합니다.

이 정보도 화면 표시에만 쓰이고, 설치 폴더 밖이나 인터넷으로 보내지 않습니다.

## 제3자 제공·판매

없습니다. 광고, 분석 도구, 추적 코드도 없습니다.

## 삭제

TaskPet을 제거하면(로봇 우클릭 → TaskPet 제거, 또는 Windows 설정 → 앱) 설치 폴더와 추가했던 설정이 지워집니다. 확장은 브라우저 확장 페이지에서 삭제하면 됩니다.

## 문의

GitHub 이슈: https://github.com/rladleh0729-del/TaskPet/issues

---

## English

TaskPet (Windows app) and the TaskPet for AI Chats browser extension **do not send any data** to the developer or anyone else. Everything stays on your computer.

The extension runs only on chatgpt.com, gemini.google.com, claude.ai, grok.com and kimi.ai (kimi.com). It only checks whether the input box shows a "Stop" button (to know if the AI is still answering), plus the current conversation's title, URL and tab id. It **never reads message content**, cookies, account data or browsing history. That state is passed via Native Messaging to the TaskPet app on the same computer only, and is used solely to show the status bubble and to switch back to the tab.

The Windows app reads local Claude Code hook signals, Codex session logs, and the ChatGPT desktop app's "working" indicator via Windows UI Automation, for display only. No data is sold or shared; there are no ads, analytics or trackers. Uninstalling removes the app folder and the settings it added.

Contact: https://github.com/rladleh0729-del/TaskPet/issues
