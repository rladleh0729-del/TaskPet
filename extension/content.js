// TaskPet — 이 탭의 ChatGPT / Gemini / Claude / Grok / Kimi가 답을 쓰는 중인지 살펴서 TaskPet 로봇에게 알린다.
// 대화 내용은 읽지 않는다. 보내는 것: 사이트, 답변 중/끝남, 대화 주소(id), 대화 제목.

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
        || hasStopButton('form button[aria-label], #thread-bottom button[aria-label]');
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
check();

// TaskPet 연결 상태를 물어봐서 표시 (연결됨 / 오류 내용)
function hello() {
  try {
    chrome.runtime.sendMessage({ type: 'hello' }, (r) => {
      root.dataset.taskpetLink = chrome.runtime.lastError ? '확장 오류: ' + chrome.runtime.lastError.message
        : (r && r.connected ? '연결됨' : '연결 안 됨: ' + ((r && r.error) || '알 수 없음'));
    });
  } catch (e) {
    root.dataset.taskpetLink = '확장 다시 불러와짐: 새로 고침 필요';
  }
}
hello();
setInterval(hello, 10000);
