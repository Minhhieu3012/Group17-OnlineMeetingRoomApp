// Helpers & WS login bridge (dùng chung cho 3 trang)

export const RE_USERNAME = /^[a-z0-9_]{1,24}$/;
export const RE_GMAIL = /^[A-Za-z0-9._%+-]+@gmail\.com$/;

export const $ = (sel) => document.querySelector(sel);
export function el(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v;
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) n.setAttribute(k, v);
  }
  for (const c of children) n.append(c);
  return n;
}

export function getWsUrl() {
  return localStorage.getItem('ws_url') || (location.origin.replace(/^http/, 'ws') + '/ws-app');
}

export function saveCreds({ username, email }) {
  sessionStorage.setItem('username', username);
  sessionStorage.setItem('email', email);
}
export function readCreds() {
  return {
    username: sessionStorage.getItem('username') || '',
    email: sessionStorage.getItem('email') || '',
  };
}
export function ensureCredsOrRedirect() {
  const c = readCreds();
  if (!RE_USERNAME.test(c.username) || !RE_GMAIL.test(c.email)) {
    location.href = 'login.html';
    return null;
  }
  return c;
}
export function setRoom(name){ if (name) sessionStorage.setItem('room', name); }
export function getRoom(){ return sessionStorage.getItem('room') || ''; }

// WS connect + auto login + callbacks + auto-reconnect
export function connectAndLogin(creds, handlers = {}) {
  let retries = 0;
  const maxDelay = 10000;
  const url = getWsUrl();
  let ws = null;

  const connect = () => {
    ws = new WebSocket(url);

    ws.onopen = () => {
      retries = 0;
      ws.send(JSON.stringify({ type: 'login', username: creds.username, email: creds.email }));
    };

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.ok === false && msg.type === 'login') {
        handlers.onLoginError && handlers.onLoginError(msg.error || 'Đăng nhập thất bại');
        return;
      }
      if (msg.type === 'login') { handlers.onLoginOk && handlers.onLoginOk(msg); return; }
      handlers.onMessage && handlers.onMessage(msg);
    };

    ws.onclose = () => {
      const delay = Math.min(1000 * 2 ** retries, maxDelay);
      setTimeout(connect, delay);
      retries++;
      handlers.onClose && handlers.onClose();
    };
  };

  connect();
  return new Proxy({}, {
    get: (_, prop) => (prop === 'send' ? (data) => ws && ws.readyState === 1 && ws.send(data) : undefined)
  });
}

export function renderRooms(ul, rooms, onJoin) {
  ul.innerHTML = '';
  rooms.forEach((r) => {
    ul.append(
      el('li', {}, [
        el('span', { class: 'pill' }, [document.createTextNode(`${r.room} (${r.count})`)]),
        el('button', { onclick: () => onJoin(r.room) }, ['Tham gia'])
      ])
    );
  });
}

export function renderUsers(ul, users) {
  ul.innerHTML = '';
  users.forEach((u) => ul.append(el('li', {}, [document.createTextNode(u.username)])));
}
