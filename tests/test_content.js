// content.js 를 가짜 페이지에서 돌려, 끝난 뒤 제목 갱신·다른 대화로 옮겼을 때 동작을 시험한다.
//   node tests\test_content.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const src = fs.readFileSync(path.join(__dirname, '..', 'extension', 'content.js'), 'utf8');
let now = 1000000;
let busy = false;
const sent = [];
const page = { pathname: '/', title: 'ChatGPT', sidebar: {} };   // sidebar: 대화 id → 목록 제목

const ctx = {
  location: { hostname: 'chatgpt.com', get pathname() { return page.pathname; },
              get href() { return 'https://chatgpt.com' + page.pathname; } },
  document: {
    get title() { return page.title; },
    documentElement: { dataset: {} },
    querySelector(sel) {
      if (sel === 'button[data-testid="stop-button"]') return busy ? {} : null;
      const m = sel.match(/\/c\/([\w-]+)"\]$/);
      if (m && page.sidebar[m[1]]) return { textContent: page.sidebar[m[1]] };
      return null;
    },
    querySelectorAll() { return []; },
  },
  MutationObserver: class { observe() {} },
  setInterval() {}, setTimeout, clearTimeout,
  chrome: { runtime: { sendMessage(m, cb) { if (m.type === 'state') sent.push(m); else if (cb) cb({ connected: true }); },
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
console.log('통과', sent.map(m => m.state + ':' + m.title));
