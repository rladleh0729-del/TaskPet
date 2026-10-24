// TaskPet — 이 탭의 ChatGPT / Gemini가 답을 쓰는 중인지 살펴서 TaskPet 로봇에게 알린다.
// 대화 내용은 읽지 않는다. 보내는 것: 사이트, 답변 중/끝남, 대화 주소(id), 대화 제목.

const STOP_LABEL = /^(stop|중지|응답 중지|스트리밍 중지|대답 생성 중지|stop streaming|stop response|停止)/i;
const DONE_DELAY = 1500;   // 잠깐 멈췄다가 다시 쓰는 경우가 있어 이만큼 조용해야 끝으로 본다

function hasStopButton(selector) {
  for (const b of document.querySelectorAll(selector)) {
    const label = (b.getAttribute('aria-label') || '').trim();
    if (STOP_LABEL.test(label)) return true;
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
};
const SITE = location.hostname.includes('gemini.google.com') ? 'gemini' : 'chatgpt';
const S = SITES[SITE];

function title() {
  const id = S.conv();
  if (id) {
    const a = document.querySelector(S.link(id));
    const t = a && a.textContent.trim();
    if (t) return t.slice(0, 80);
  }
  const t = document.title.trim();
  return t && t !== S.plainTitle ? t.slice(0, 80) : '새 채팅';
}

let state = 'idle';
let quietSince = 0;
let lastSent = '';

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
    }
  }
}

// 화면이 바뀔 때마다 확인하고, 뒤쪽 탭에서 화면 갱신이 줄어드는 경우를 대비해 1초마다도 확인
new MutationObserver(check).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-label', 'data-testid', 'class', 'fonticon'] });
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
