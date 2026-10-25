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
  if (fresh && port && msg.state !== 'closed') return;
  try { if (port) port.postMessage(msg); } catch (e) { port = null; }
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg && msg.type === 'state' && sender.tab) {
    send({ ...msg, tab: sender.tab.id });
  } else if (msg && msg.type === 'hello') {
    connect();
    // 연결 결과는 조금 뒤에 정해지므로 잠깐 기다렸다 답한다
    setTimeout(() => reply({ connected: !!port, error: lastError }), 700);
    return true;
  }
});

chrome.tabs.onRemoved.addListener((tabId) => send({ type: 'state', state: 'closed', tab: tabId }));

async function onHost(msg) {
  if (!msg || msg.cmd !== 'open') return;
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

// 처음 설치하면 TaskPet(Windows 프로그램) 받는 페이지를 연다 — 확장만으로는 로봇이 없어서 아무것도 안 보이므로
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') chrome.tabs.create({ url: 'https://querybot.kr/taskpet/#install' });
});

connect();
