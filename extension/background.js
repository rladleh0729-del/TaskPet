// TaskPet for AI Chats — 탭에서 받은 상태를 Native Messaging으로 TaskPet에 전달하고,
// TaskPet에서 줄을 더블 클릭하면 그 탭을 앞으로 가져온다.
const HOST = 'kr.querybot.taskpet';
let port = null;
let retry = null;
let lastError = '';
// 탭마다 마지막으로 받은 상태. TaskPet과 연결이 끊겼다 다시 붙으면 한꺼번에 다시 보낸다
// (끊긴 사이에 보낸 상태가 사라지지 않게)
const latest = {};

function connect() {
  if (port) return;
  try {
    port = chrome.runtime.connectNative(HOST);
  } catch (e) {
    port = null;
    lastError = String(e && e.message || e);
    return;
  }
  port.onMessage.addListener(onHost);
  for (const m of Object.values(latest)) {
    try { port.postMessage(m); } catch (e) { /* 곧 onDisconnect 로 감 */ }
  }
  port.onDisconnect.addListener(() => {
    // TaskPet이 설치 안 돼 있거나 등록이 잘못되면 여기로 온다
    lastError = (chrome.runtime.lastError && chrome.runtime.lastError.message) || '연결 끊김';
    port = null;
    clearTimeout(retry);
    retry = setTimeout(connect, 15000);
  });
}

function send(msg) {
  if (msg.type === 'state' && msg.tab !== undefined) {
    if (msg.state === 'closed') delete latest[msg.tab];
    else latest[msg.tab] = msg;
  }
  const fresh = !port;
  connect();                       // 새로 연결되면 connect 안에서 latest 를 모두 보냄
  // (다시 보내지는 건 탭 상태뿐이라, 대화 글·보낸 결과는 새 연결로 바로 보낸다)
  if (fresh && port && msg.type === 'state' && msg.state !== 'closed') return;
  try { if (port) port.postMessage(msg); } catch (e) { port = null; }
}

// 로봇에서 지금 펼쳐 보고 있는 탭 → 마지막으로 watch 가 온 시각. 로봇이 20초마다 다시 알려 주므로,
// 60초 넘게 소식이 없으면(로봇이 갑자기 꺼짐 등) 그 탭은 그만 보낸다
const watched = new Map();
const WATCH_TTL = 60000;
const isWatched = (tab) => watched.has(tab) && Date.now() - watched.get(tab) < WATCH_TTL;
setInterval(() => {
  for (const [tab, at] of watched) {
    if (Date.now() - at < WATCH_TTL) continue;
    watched.delete(tab);
    chrome.tabs.sendMessage(tab, { type: 'watch', on: false }).catch(() => {});
  }
}, 15000);

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg && (msg.type === 'state' || msg.type === 'chat') && sender.tab) {
    if (msg.type === 'chat' && !isWatched(sender.tab.id)) return;
    send({ ...msg, tab: sender.tab.id });
  } else if (msg && msg.type === 'hello') {
    connect();
    // 연결 결과는 조금 뒤에 정해지므로 잠깐 기다렸다 답한다
    const tab = sender.tab ? sender.tab.id : -1;
    setTimeout(() => reply({ connected: !!port, error: lastError, watched: isWatched(tab) }), 700);
    return true;
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  watched.delete(tabId);
  send({ type: 'state', state: 'closed', tab: tabId });
});

async function onHost(msg) {
  if (!msg) return;
  if (msg.cmd === 'watch' || msg.cmd === 'unwatch' || msg.cmd === 'send') {
    // 같은 브라우저의 다른 프로필도 같은 명령을 받는다 → 이 프로필의 탭이 아니면 아무것도 안 함(답도 안 함)
    try { await chrome.tabs.get(msg.tab); } catch (e) { return; }
  }
  if (msg.cmd === 'watch' || msg.cmd === 'unwatch') {
    const on = msg.cmd === 'watch';
    if (on) watched.set(msg.tab, Date.now()); else watched.delete(msg.tab);
    try { await chrome.tabs.sendMessage(msg.tab, { type: 'watch', on }); } catch (e) { /* 탭이 없거나 아직 준비 안 됨 */ }
    return;
  }
  if (msg.cmd === 'send') {
    // 로봇 입력칸에 쓴 글을 그 탭 입력창에 넣고 보낸다. 결과는 로봇에게 돌려준다
    let r;
    try {
      r = await chrome.tabs.sendMessage(msg.tab, { type: 'send', text: msg.text });
    } catch (e) {
      r = { ok: false, error: 'no_tab' };
    }
    send({ type: 'sent', tab: msg.tab, id: msg.id, ok: !!(r && r.ok), error: (r && r.error) || '' });
    return;
  }
  if (msg.cmd !== 'open') return;
  try {
    const tab = await chrome.tabs.update(msg.tab, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
  } catch (e) {
    // 탭이 이미 닫혔으면 그 대화를 새 탭으로 연다
    const url = msg.url || (msg.conv ? `https://chatgpt.com/c/${msg.conv}` : 'https://chatgpt.com/');
    const tab = await chrome.tabs.create({ url });
    await chrome.windows.update(tab.windowId, { focused: true });
  }
}

// 처음 설치하면 TaskPet(Windows 프로그램) 받는 페이지를 연다 — 확장만으로는 로봇이 없어서 아무것도 안 보이므로.
// 브라우저가 한국어가 아니면 영어 페이지로
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason !== 'install') return;
  const lang = /^ko/i.test(chrome.i18n.getUILanguage()) ? 'ko' : 'en';
  chrome.tabs.create({ url: `https://querybot.kr/taskpet/?lang=${lang}#install` });
});

connect();
