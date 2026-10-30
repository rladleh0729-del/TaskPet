// TaskPet — 이 탭의 ChatGPT / Gemini / Claude / Grok / Kimi가 답을 쓰는 중인지 살펴서 TaskPet 로봇에게 알린다.
// 늘 보내는 것: 사이트, 답변 중/끝남, 대화 주소(id), 대화 제목.
// 대화 글은 사용자가 로봇에서 이 탭 줄을 펼쳐 보는 동안에만 읽어 보낸다(아래 '로봇에서 대화 보기').
// 어느 쪽이든 같은 컴퓨터의 TaskPet 프로그램에만 가고, 인터넷으로는 아무것도 보내지 않는다.

// '중지' 버튼 이름 (Claude·Grok 은 이 이름으로만 답하는 중인지 안다) — 사이트 화면이 어느 언어여도 잡히게:
// 한중일 글자(중지·停止·中止)는 어디에 있어도, 나머지 말은 낱말 첫머리면 '중지'로 본다.
// 단, 받아쓰기·음성·녹음 버튼('받아쓰기 중지', 'Stop dictation' 등)은 뺀다
const STOP_CJK = /중지|停止|中止|ストップ/;
const STOP_WORD = /(?<![\p{L}\p{N}])(stop|detener|parar|interromp|arr[êe]t|anhalten|abbrechen|ferma|zatrzym|останов|стоп|hentikan|dừng|durdur)/iu;
const NOT_STOP = /dict|diktat|diktier|ditad|dettat|voice|voz|voix|voce|stimme|sprach|голос|диктов|음성|받아쓰기|녹음|音声|録音|ディクテーション|语音|語音|录音|錄音|听写|聽寫|record|enregistr|aufnahme|grava|graba|registra|запис/i;
const DONE_DELAY = 1500;   // 잠깐 멈췄다가 다시 쓰는 경우가 있어 이만큼 조용해야 끝으로 본다

function isStopLabel(label) {
  return (STOP_CJK.test(label) || STOP_WORD.test(label)) && !NOT_STOP.test(label);
}

function hasStopButton(selector) {
  for (const b of document.querySelectorAll(selector)) {
    if (isStopLabel((b.getAttribute('aria-label') || '').trim())) return true;
  }
  return false;
}

const SITES = {
  chatgpt: {
    // 입력창 근처에 '중지' 버튼이 있으면 답을 쓰는 중
    generating() {
      return !!document.querySelector('button[data-testid="stop-button"]')
        || hasStopButton('form button[aria-label], #thread-bottom button[aria-label], [data-chatgpt-composer] button[aria-label]');
    },
    conv() {
      const m = location.pathname.match(/\/c\/([\w-]+)/);
      return m ? m[1] : '';
    },
    // 제목은 왼쪽 목록의 그 대화 줄 이름이 가장 정확하다 (탭 제목은 'ChatGPT'일 때가 많음)
    link: (id) => `nav a[href$="/c/${id}"]`,
    plainTitle: 'ChatGPT',
  },
  gemini: {
    // 답하는 동안 보내기 버튼이 '대답 생성 중지' 버튼(아이콘 stop)으로 바뀐다
    generating() {
      return !!document.querySelector('input-area-v2 button.stop, input-area-v2 mat-icon[fonticon="stop"]')
        || hasStopButton('input-area-v2 button[aria-label], .input-area button[aria-label]');
    },
    conv() {
      const m = location.pathname.match(/\/app\/([\w-]+)/);
      return m ? m[1] : '';
    },
    link: (id) => `a[href$="/app/${id}"]`,
    plainTitle: 'Google Gemini',
  },
  claude: {
    // 답하는 동안 입력창의 보내기 버튼이 '응답 중지' 버튼으로 바뀐다
    generating: () => editorHasStop(),
    conv() {
      const m = location.pathname.match(/\/chat\/([\w-]+)/);
      return m ? m[1] : '';
    },
    link: (id) => `a[href$="/chat/${id}"]`,
    plainTitle: 'Claude',
  },
  grok: {
    generating: () => editorHasStop(),
    conv() {
      const m = location.pathname.match(/\/c\/([\w-]+)/);
      return m ? m[1] : '';
    },
    link: (id) => `a[href*="/c/${id}"]`,
    plainTitle: 'Grok',
  },
  kimi: {
    // 버튼에 이름이 없다. 보내기 상자 안 아이콘이 평소 name="Send" → 답하는 동안 다른 아이콘(중지)
    generating() {
      const box = document.querySelector('.send-button-container');
      if (!box) return false;
      if (/stop|pause/i.test(box.className)) return true;
      const icon = box.querySelector('svg[name]');
      return !!icon && !/^send$/i.test(icon.getAttribute('name'));
    },
    conv() {
      const m = location.pathname.match(/\/chat\/([\w-]+)/);
      return m && m[1] !== 'history' ? m[1] : '';
    },
    link: (id) => `a[href*="/chat/${id}"]`,
    plainTitle: 'Kimi',
  },
};

// 입력창(글 쓰는 칸)을 감싼 form / 상자 안에 '중지' 버튼이 있는지
function editorHasStop() {
  const ed = document.querySelector('[contenteditable="true"], textarea');
  if (!ed) return false;
  let box = ed.closest('form, fieldset');
  if (!box) {
    box = ed;
    for (let i = 0; i < 8 && box.parentElement; i++) box = box.parentElement;
  }
  for (const b of box.querySelectorAll('button[aria-label]')) {
    if (isStopLabel(b.getAttribute('aria-label').trim())) return true;
  }
  return false;
}

const HOST = location.hostname;
const SITE = HOST.includes('gemini.google.com') ? 'gemini'
  : HOST.endsWith('claude.ai') ? 'claude'
  : HOST.endsWith('grok.com') ? 'grok'
  : /kimi\.(ai|com)$|kimi\.moonshot\.cn$/.test(HOST) ? 'kimi' : 'chatgpt';
const S = SITES[SITE];

function title() {
  const id = S.conv();
  if (id) {
    const a = document.querySelector(S.link(id));
    const t = a && a.textContent.trim();
    if (t) return t.slice(0, 80);
  }
  // 탭 제목에서 ' - Claude' 같은 사이트 이름 꼬리는 뗀다
  const t = document.title.trim().replace(new RegExp(`\\s*[-–|]\\s*${S.plainTitle}$`), '');
  return t && t !== S.plainTitle && t !== '새 세션' && t !== 'New session' ? t.slice(0, 80) : newChatName();
}

// 제목 없는 새 채팅 이름 — 브라우저 언어로 (_locales/*/messages.json 의 newChat)
function newChatName() {
  try { return chrome.i18n.getMessage('newChat') || 'New chat'; } catch (e) { return 'New chat'; }
}

const TITLE_WAIT = 60000; // 새 채팅은 답이 끝난 뒤에 제목이 붙기도 해서, 이만큼은 제목 변화를 더 본다

let state = 'idle';
let quietSince = 0;
let lastSent = '';
let doneAt = 0;           // 마지막으로 '끝남'을 알린 시각
let doneConv = '';        // 그때의 대화 id (다른 대화로 옮겨 가면 제목 갱신을 보내지 않음)

function report(s) {
  const msg = { type: 'state', site: SITE, state: s, conv: S.conv(), title: title(), url: location.href };
  const key = JSON.stringify([msg.state, msg.conv, msg.title]);
  if (key === lastSent) return;
  lastSent = key;
  try { chrome.runtime.sendMessage(msg); } catch (e) { /* 확장이 다시 불러와진 직후 */ }
}

// 문제를 찾기 쉽게 상태를 페이지에 표시해 둔다 (html 태그의 data-taskpet-* 속성)
const root = document.documentElement;

function check() {
  const now = Date.now();
  const busy = S.generating();
  root.dataset.taskpetState = state + (busy ? '/중지버튼' : '');
  if (busy) {
    quietSince = 0;
    if (state !== 'working') state = 'working';
    report('working');          // 제목이 생기거나 바뀌면 다시 알림
  } else if (state === 'working') {
    if (!quietSince) quietSince = now;
    if (now - quietSince >= DONE_DELAY) {
      state = 'idle';
      report('done');
      doneAt = now;
      doneConv = S.conv();
    }
  } else if (doneAt && now - doneAt < TITLE_WAIT) {
    // 끝난 뒤 같은 대화(또는 새 채팅에 막 생긴 id)의 제목이 바뀌면 한 번 더 알림 (같은 내용이면 report가 거름)
    const conv = S.conv();
    if (conv === doneConv || !doneConv) report('done');
    if (conv && !doneConv) doneConv = conv;
  }
  reportChat(false);           // 로봇에서 이 탭을 보고 있으면 대화 글도
}

// 답이 한 글자씩 나올 때마다 화면이 바뀌므로, 검사는 0.25초에 한 번으로 묶는다
let pending = null;
function scheduleCheck() {
  if (pending) return;
  pending = setTimeout(() => { pending = null; check(); }, 250);
}

// 화면이 바뀔 때마다 확인하고, 뒤쪽 탭에서 화면 갱신이 줄어드는 경우를 대비해 1초마다도 확인
new MutationObserver(scheduleCheck).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-label', 'data-testid', 'class', 'fonticon', 'name'] });
setInterval(check, 1000);

// ---- 로봇에서 대화 보기 · 답 보내기 ----
// 로봇에서 이 탭 줄을 펼치면(watch) 그동안만 대화 글을 읽어 로봇에게 보낸다 — 화면이 바뀔 때, 0.7초에 한 번까지.
// 로봇 입력칸에 쓴 글은 이 탭 입력창에 붙여 넣고 보내기 버튼을 누른다.
const MAX_MSGS = 24;       // 최근 메시지 몇 개까지
const MAX_TEXT = 6000;     // 메시지 하나는 끝에서 이만큼까지
const SEND_LABEL = /send|submit|보내|전송|제출|送信|发送|發送|傳送|提交|enviar|envoyer|senden|отправ|invia|kirim|gửi|gönder/i;
// 메시지 칸 안의 화면 읽기용 숨은 제목('말씀하신 내용'·'Claude 응답: …'), 버튼·시각('지금') 글자는 뺀다
const HIDDEN = '.sr-only, .cdk-visually-hidden, [class*="visually-hidden"], button, [role="button"], time';
function textOf(el) {
  if (!el) return '';
  let t = el.innerText || el.textContent || '';
  for (const h of (el.querySelectorAll ? el.querySelectorAll(HIDDEN) : [])) {
    const x = (h.innerText || h.textContent || '').trim();
    if (x) t = t.replace(x, '');
  }
  return t.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

// 보내기 버튼: 이름(aria-label)으로 찾되 음성·중지 버튼은 뺀다
function sendByLabel(selector) {
  for (const b of document.querySelectorAll(selector)) {
    const label = b.getAttribute('aria-label') || '';
    if (b.offsetParent && SEND_LABEL.test(label) && !NOT_STOP.test(label) && !isStopLabel(label)) return b;
  }
  return null;
}

// 사이트마다: msgs() = [['me'|'ai', 글], ...] (위에서부터), editor() = 입력창, send() = 보내기 버튼
const CHAT = {
  chatgpt: {
    msgs() {
      const turns = document.querySelectorAll('[data-turn-key]');
      if (turns.length) {
        const out = [];
        for (const tn of turns) {
          const u = tn.querySelector('[data-user-message-bubble]');
          if (u) out.push(['me', textOf(u)]);
          const a = tn.querySelector('[data-chatgpt-selection-message-id]');
          if (a) out.push(['ai', textOf(a)]);
        }
        return out;
      }
      return [...document.querySelectorAll('[data-message-author-role="user"], [data-message-author-role="assistant"]')]
        .map(m => [m.dataset.messageAuthorRole === 'user' ? 'me' : 'ai',
                   textOf(m.querySelector('.markdown, .whitespace-pre-wrap') || m)]);
    },
    editor: () => document.querySelector('[data-composer-input] [contenteditable="true"], #prompt-textarea, .ProseMirror[contenteditable="true"]'),
    send: () => document.querySelector('button[data-testid="send-button"], #composer-submit-button')
      || sendByLabel('[data-chatgpt-composer] button, form button'),
  },
  claude: {
    msgs: () => [...document.querySelectorAll('[data-testid="user-message"], [data-testid="assistant-message"]')]
      .map(m => [m.dataset.testid === 'user-message' ? 'me' : 'ai', textOf(m)]),
    editor: () => document.querySelector('[data-testid="chat-input"][contenteditable="true"], [data-testid="chat-input"] [contenteditable="true"], .ProseMirror[contenteditable="true"]'),
    send: () => document.querySelector('button[data-testid="chat-input-send"]') || sendByLabel('fieldset button, form button'),
  },
  gemini: {
    msgs: () => [...document.querySelectorAll('user-query, model-response')]
      .map(m => m.tagName === 'USER-QUERY' ? ['me', textOf(m.querySelector('.query-text') || m)]
                                           : ['ai', textOf(m.querySelector('message-content') || m)]),
    editor: () => document.querySelector('rich-textarea [contenteditable="true"], .ql-editor[contenteditable="true"]'),
    send: () => document.querySelector('button.send-button') || sendByLabel('input-area-v2 button, .input-area button'),
  },
  grok: {
    // 내 메시지 줄은 오른쪽 정렬(items-end), 답은 왼쪽
    msgs: () => [...document.querySelectorAll('[id^="response-"]')]
      .map(r => [/\bitems-end\b/.test(r.className) ? 'me' : 'ai', textOf(r.querySelector('.message-bubble') || r)]),
    editor: () => document.querySelector('.tiptap.ProseMirror[contenteditable="true"], form textarea'),
    send: () => document.querySelector('form button[type="submit"]') || sendByLabel('form button'),
  },
  kimi: {
    msgs: () => [...document.querySelectorAll('.chat-content-item')]
      .map(m => [/user/.test(m.className) ? 'me' : 'ai', textOf(m.querySelector('.segment-content-box, .markdown') || m)]),
    editor: () => document.querySelector('.chat-input-editor[contenteditable="true"], .chat-input-editor'),
    send: () => document.querySelector('.send-button-container'),
  },
};
const C = CHAT[SITE];

let watching = false;
let lastChat = '';
let lastChatAt = 0;

function reportChat(force) {
  if (!watching) return;
  const now = Date.now();
  if (!force && now - lastChatAt < 700) return;   // 답이 한 글자씩 나오는 동안엔 0.7초에 한 번
  let msgs = [];
  try { msgs = C.msgs(); } catch (e) { /* 사이트 화면이 바뀌었으면 빈 목록 */ }
  msgs = msgs.filter(m => m[1]).slice(-MAX_MSGS)
    .map(([r, t]) => [r, t.length > MAX_TEXT ? '…' + t.slice(-MAX_TEXT) : t]);
  const working = state === 'working';
  const key = JSON.stringify([working, msgs]);
  if (key === lastChat && !force) return;
  lastChat = key;
  lastChatAt = now;
  try { chrome.runtime.sendMessage({ type: 'chat', site: SITE, conv: S.conv(), title: title(), working, msgs }); } catch (e) { /* 확장 다시 불러와짐 */ }
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function waitFor(fn, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) { const v = fn(); if (v) return v; await sleep(100); }
  return fn();
}
const editorText = (ed) => (ed.tagName === 'TEXTAREA' ? ed.value : ed.innerText || '').trim();
function setTextarea(ed, v) {
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(ed, v);
  ed.dispatchEvent(new Event('input', { bubbles: true }));
}

// 결과의 error 는 로봇이 자기 언어로 바꿔 보여 줄 짧은 이름
async function sendText(msg) {
  const ed = C.editor();
  if (!ed) return { ok: false, error: 'no_editor' };
  if (S.generating()) return { ok: false, error: 'busy' };
  if (editorText(ed)) return { ok: false, error: 'draft' };     // 그 탭에 쓰던 글은 건드리지 않는다
  ed.focus();
  if (ed.tagName === 'TEXTAREA') {
    setTextarea(ed, msg);
  } else {
    // 붙여 넣기로 넣으면 여러 줄도 그대로 들어간다 (안 되는 사이트는 글자 넣기로)
    const dt = new DataTransfer();
    dt.setData('text/plain', msg);
    ed.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    await sleep(150);
    if (!editorText(ed)) document.execCommand('insertText', false, msg);
  }
  const btn = await waitFor(() => {
    const b = C.send();
    return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true' ? b : null;
  }, 3000);
  if (!btn) return { ok: false, error: 'no_send' };
  btn.click();
  const sent = await waitFor(() => !editorText(C.editor() || ed) || S.generating(), 4000);
  return sent ? { ok: true } : { ok: false, error: 'not_sent' };
}

chrome.runtime.onMessage.addListener((m, sender, reply) => {
  if (!m) return;
  if (m.type === 'watch') {
    watching = !!m.on;
    if (watching) { lastChat = ''; reportChat(true); }
  } else if (m.type === 'send') {
    sendText(String(m.text || '')).then(reply, (e) => reply({ ok: false, error: 'error: ' + e }));
    return true;
  }
});

// TaskPet 연결 상태를 물어봐서 표시 (연결됨 / 오류 내용). 로봇이 이 탭을 보고 있는지도 함께 받는다
// (페이지를 새로 고쳤거나 확장이 다시 불러와져도 이어서 보내도록)
function hello() {
  try {
    chrome.runtime.sendMessage({ type: 'hello' }, (r) => {
      root.dataset.taskpetLink = chrome.runtime.lastError ? '확장 오류: ' + chrome.runtime.lastError.message
        : (r && r.connected ? '연결됨' : '연결 안 됨: ' + ((r && r.error) || '알 수 없음'));
      if (r && !chrome.runtime.lastError) {
        const was = watching;
        watching = !!r.watched;
        if (watching && !was) { lastChat = ''; reportChat(true); }
      }
    });
  } catch (e) {
    root.dataset.taskpetLink = '확장 다시 불러와짐: 새로 고침 필요';
  }
}
check();
hello();
setInterval(hello, 10000);
