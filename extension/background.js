// TaskPet for AI Chats — 탭에서 받은 상태를 Native Messaging으로 TaskPet에 전달하고,
// TaskPet에서 줄을 더블 클릭하면 그 탭을 앞으로 가져온다.
const HOST = 'kr.querybot.taskpet';
let port = null;
let retry = null;
let lastError = '';

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
  port.onDisconnect.addListener(() => {
    // TaskPet이 설치 안 돼 있거나 등록이 잘못되면 여기로 온다
    lastError = (chrome.runtime.lastError && chrome.runtime.lastError.message) || '연결 끊김';
    port = null;
    clearTimeout(retry);
    retry = setTimeout(connect, 15000);
  });
}

function send(msg) {
  connect();
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

connect();
