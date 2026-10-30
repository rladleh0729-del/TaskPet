// content.js 를 가짜 페이지에서 돌려, 끝난 뒤 제목 갱신·다른 대화로 옮겼을 때 동작과
// 로봇에서 펼쳐 볼 때의 대화 글 보내기·로봇에서 쓴 답 보내기를 시험한다.
//   node tests\test_content.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'extension', 'content.js'), 'utf8');
let now = 1000000;
let busy = false;
const sent = [];
const chats = [];
let listener = null;
const page = { pathname: '/', title: 'ChatGPT', sidebar: {} };   // sidebar: 대화 id → 목록 제목

// 가짜 대화 (ChatGPT 새 화면: 턴마다 내 말풍선 + 답)
const turn = (me, ai) => ({
  querySelector(sel) {
    if (sel === '[data-user-message-bubble]') return me === null ? null : { innerText: me };
    if (sel === '[data-chatgpt-selection-message-id]') return ai === null ? null : { innerText: ai };
    return null;
  },
});
page.turns = [];
// 가짜 입력창·보내기 버튼
const editor = { tagName: 'DIV', innerText: '', focus() {}, dispatchEvent(ev) { if (ev.type === 'paste') { editor.innerText = ev.clipboardData.getData('text/plain'); ev.defaultPrevented = true; } } };
let sendClicks = 0;
const sendButton = { disabled: false, getAttribute: () => null, click() { sendClicks++; editor.innerText = ''; } };

const ctx = {
  location: { hostname: 'chatgpt.com', get pathname() { return page.pathname; },
              get href() { return 'https://chatgpt.com' + page.pathname; } },
  document: {
    get title() { return page.title; },
    documentElement: { dataset: {} },
    querySelector(sel) {
      if (sel === 'button[data-testid="stop-button"]') return busy ? {} : null;
      if (sel.startsWith('[data-composer-input]')) return editor;
      if (sel.startsWith('button[data-testid="send-button"]')) return editor.innerText ? sendButton : null;
      const m = sel.match(/\/c\/([\w-]+)"\]$/);
      if (m && page.sidebar[m[1]]) return { textContent: page.sidebar[m[1]] };
      return null;
    },
    querySelectorAll(sel) { return sel === '[data-turn-key]' ? page.turns : []; },
    execCommand() {},
  },
  MutationObserver: class { observe() {} },
  setInterval() {}, setTimeout, clearTimeout, Promise,
  DataTransfer: class { constructor() { this.d = {}; } setData(k, v) { this.d[k] = v; } getData(k) { return this.d[k]; } },
  ClipboardEvent: class { constructor(type, o) { this.type = type; this.clipboardData = o.clipboardData; } },
  Event: class { constructor(type) { this.type = type; } },
  chrome: { runtime: { sendMessage(m, cb) { if (m.type === 'state') sent.push(m); else if (m.type === 'chat') chats.push(m); else if (cb) cb({ connected: true }); },
                       onMessage: { addListener(fn) { listener = fn; } },
                       lastError: null },
            i18n: { getMessage: (k) => (k === 'newChat' ? '새 채팅' : '') } },   // 한국어 브라우저 흉내
  Date: { now: () => now },
  RegExp, JSON, console,
};
vm.createContext(ctx);
vm.runInContext(src, ctx);
const step = (ms) => { now += ms; vm.runInContext('check()', ctx); };
const last = () => sent[sent.length - 1];

busy = true; step(10);                                   // 새 채팅에서 답하는 중
if (last().state !== 'working' || last().title !== '새 채팅') throw new Error('working ' + JSON.stringify(last()));
busy = false; step(500); step(1600);                     // 1.5초 조용 → 끝남
if (last().state !== 'done') throw new Error('done');
const n = sent.length;
page.pathname = '/c/abc'; page.sidebar.abc = '여행 계획'; step(2000);   // 끝난 뒤 주소·제목이 생김
if (sent.length !== n + 1 || last().title !== '여행 계획' || last().conv !== 'abc') throw new Error('title ' + JSON.stringify(last()));
step(1000);                                              // 같은 내용은 다시 안 보냄
if (sent.length !== n + 1) throw new Error('dup');
page.pathname = '/c/zzz'; page.sidebar.zzz = '다른 대화'; step(1000);  // 다른 대화로 옮김 → 안 보냄
if (sent.length !== n + 1) throw new Error('other conv ' + JSON.stringify(last()));
page.pathname = '/c/abc'; page.sidebar.abc = '여행 계획 (수정)'; step(70000);  // 1분 지나면 더는 안 봄
if (sent.length !== n + 1) throw new Error('after wait');
console.log('통과', sent.map(m => m.state + ':' + m.title));

// '중지' 버튼 이름: 여러 언어의 응답 중지는 잡고, 받아쓰기·녹음 중지나 다른 버튼은 안 잡는다
const stop = (l) => vm.runInContext(`isStopLabel(${JSON.stringify(l)})`, ctx);
for (const l of ['응답 중지', '모델 응답 중지', 'Stop response', 'Stop generating', '応答を停止', '停止生成', '停止回應',
                 'Detener respuesta', 'Parar resposta', 'Interromper', 'Arrêter la réponse', 'Antwort stoppen', 'Stopp',
                 'Interrompi la risposta', 'Остановить ответ', 'Стоп', 'Hentikan respons', 'Dừng phản hồi', 'Yanıtı durdur']) {
  if (!stop(l)) throw new Error('중지 못 잡음: ' + l);
}
for (const l of ['받아쓰기 중지', '음성 입력 중지', 'Stop dictation', 'Stop recording', 'Stop voice mode', '音声入力を停止',
                 '停止录音', 'Detener dictado', 'Arrêter la dictée', 'Diktat stoppen', 'Остановить запись',
                 'Send', '보내기', 'Upload', 'Unstoppable', 'Bestop']) {
  if (stop(l)) throw new Error('중지로 잘못 봄: ' + l);
}

// 로봇에서 펼치기 전엔 대화 글을 안 보내고, 펼치면(watch) 보내고, 바뀔 때만 다시 (0.7초 간격), 닫으면 그만
page.turns = [turn('질문 하나', '답 하나'), turn('두 번째', null)];
step(1000);
if (chats.length) throw new Error('watch 전에 보냄');
listener({ type: 'watch', on: true });
if (chats.length !== 1 || JSON.stringify(chats[0].msgs) !== JSON.stringify([['me', '질문 하나'], ['ai', '답 하나'], ['me', '두 번째']]))
  throw new Error('watch ' + JSON.stringify(chats));
step(1000);
if (chats.length !== 1) throw new Error('같은 대화 다시 보냄');
page.turns[1] = turn('두 번째', '두 번째 답'); step(1000);
if (chats.length !== 2 || chats[1].msgs[3][1] !== '두 번째 답') throw new Error('바뀐 대화 ' + JSON.stringify(chats[1]));
listener({ type: 'watch', on: false });
page.turns.push(turn('세 번째', null)); step(1000);
if (chats.length !== 2) throw new Error('unwatch 뒤에도 보냄');

// 다시 watch 가 와도(로봇을 다시 켬) 같은 대화를 처음부터 다시 보낸다
listener({ type: 'watch', on: true });
const nAgain = chats.length;
listener({ type: 'watch', on: true });
if (chats.length !== nAgain + 1) throw new Error('다시 온 watch 에 안 보냄');
listener({ type: 'watch', on: false });

// 메시지 칸의 숨은 제목('말씀하신 내용')·버튼·시각 글자는 뺀다
const hiddenEl = (txt) => ({ innerText: txt });
const msgEl = {
  innerText: '말씀하신 내용\n안녕하세요\n\n\n\n복사\n지금',
  querySelectorAll: (sel) => (sel.includes('sr-only') ? [hiddenEl('말씀하신 내용'), hiddenEl('복사'), hiddenEl('지금')] : []),
};
const cleaned = vm.runInContext('textOf', ctx)(msgEl);
if (cleaned !== '안녕하세요') throw new Error('숨은 글 빼기 ' + JSON.stringify(cleaned));

// 로봇에서 쓴 답: 입력창에 붙여 넣고 보내기 → 입력창이 비면 성공. 그 탭에 쓰던 글이 있으면 안 보냄
const sendVia = (text) => new Promise((res) => listener({ type: 'send', text }, {}, res));
(async () => {
  const r1 = await sendVia('여러 줄\n답장');
  if (!r1.ok || sendClicks !== 1) throw new Error('보내기 ' + JSON.stringify(r1));
  editor.innerText = '쓰던 글';
  const r2 = await sendVia('또 보냄');
  if (r2.ok || r2.error !== 'draft' || sendClicks !== 1 || editor.innerText !== '쓰던 글') throw new Error('쓰던 글 ' + JSON.stringify(r2));
  editor.innerText = ''; busy = true;
  const r3 = await sendVia('답하는 중');
  if (r3.ok || r3.error !== 'busy') throw new Error('답하는 중 ' + JSON.stringify(r3));
  console.log('통과 (대화 보기·답 보내기)', chats.length, [r1, r2, r3].map(r => r.ok ? 'ok' : r.error));
})().catch((e) => { console.error(e); process.exit(1); });
