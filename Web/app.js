// --- Basic state ---
const S = {
  ws: null,
  me: null,
  room: null,
  server: (localStorage.getItem('ws_url') || (location.origin.replace(/^http/, 'ws') + '/ws-app')),
};

// --- Helpers ---
const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs={}, children=[])=>{
  const n = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v;
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
    else n.setAttribute(k,v);
  }
  for (const c of children) n.append(c);
  return n;
};
const show = (id)=>{
  document.querySelectorAll('.screen').forEach(x=>x.classList.remove('active'));
  $(id).classList.add('active');
};
const notify = (text)=>{
  const n = $('#notice');
  n.textContent = text;
  n.classList.remove('hidden');
  setTimeout(()=>n.classList.add('hidden'), 2000);
};
const addMessage = (who, text)=>{
  const box = $('#messages');
  const row = el('div', {class:'msg'}, [el('b',{},[who+': ']), document.createTextNode(text)]);
  box.append(row);
  box.scrollTop = box.scrollHeight;
};

// --- WebSocket connect ---
function openWS(){
  S.ws = new WebSocket(S.server);
  S.ws.onopen = ()=>{
    const u = $('#username').value.trim();
    const e = $('#email').value.trim();
    S.ws.send(JSON.stringify({type:'login', username:u, email:e}));
  };
  S.ws.onmessage = (ev)=>{
    const msg = JSON.parse(ev.data);
    if (msg.ok === false) {
      if (msg.type === 'login') {
        $('#login-error').textContent = msg.error;
        $('#login-error').classList.remove('hidden');
        show('#screen-login');
      }
      return;
    }
    switch(msg.type){
      case 'login':
        S.me = { user_id: msg.user_id, username: msg.username, email: msg.email };
        $('#me').textContent = `${S.me.username} (${S.me.email})`;
        $('#me2').textContent = `${S.me.username} (${S.me.email})`;
        renderRooms(msg.rooms || []);
        show('#screen-lobby');
        break;
      case 'room_list':
        renderRooms(msg.rooms || []);
        break;
      case 'create_room':
        renderRooms(msg.rooms || []);
        break;
      case 'join_room':
        S.room = msg.room;
        $('#room-name').textContent = S.room;
        renderUsers(msg.users || []);
        $('#messages').innerHTML = '';
        show('#screen-room');
        break;
      case 'user_list':
        renderUsers(msg.users || []);
        break;
      case 'user_joined':
        notify(`${msg.user} đã vào phòng`);
        requestUserList();
        break;
      case 'user_left':
        notify(`${msg.user} đã rời phòng`);
        requestUserList();
        break;
      case 'chat':
        addMessage(msg.from, msg.message);
        break;
      default:
        // ignore other server messages not in Huy's scope
        break;
    }
  };
  S.ws.onclose = ()=>{
    alert('Mất kết nối tới client gateway.');
    show('#screen-login');
  };
}

function renderRooms(rooms){
  const ul = $('#room-list'); ul.innerHTML = '';
  rooms.forEach(r=>{
    const li = el('li', {}, [
      el('span', {class:'pill'}, [document.createTextNode(`${r.room} (${r.count})`)]),
      el('button', {onclick: ()=>joinRoom(r.room)}, ['Tham gia'])
    ]);
    ul.append(li);
  });
}
function renderUsers(users){
  const ul = $('#user-list'); ul.innerHTML = '';
  users.forEach(u => {
    const li = el('li', {}, [document.createTextNode(u.username)]);
    ul.append(li);
  });
}
function requestUserList(){
  if (S.ws) S.ws.send(JSON.stringify({type:'user_list'}));
}
function joinRoom(name){
  S.ws.send(JSON.stringify({type:'join_room', room:name}));
}

// --- Events ---
$('#login-form').addEventListener('submit', (e)=>{
  e.preventDefault();
  const u = $('#username').value.trim();
  const eaddr = $('#email').value.trim();
  const unameOK = /^[a-z0-9_]{1,24}$/.test(u);
  const emailOK = /^[A-Za-z0-9._%+-]+@gmail\.com$/.test(eaddr);
  if (!unameOK){
    $('#login-error').textContent = 'Tên đăng nhập chỉ gồm a-z, 0-9, _ (tối đa 24).';
    $('#login-error').classList.remove('hidden');
    return;
  }
  if (!emailOK){
    $('#login-error').textContent = 'Chỉ chấp nhận địa chỉ @gmail.com hợp lệ.';
    $('#login-error').classList.remove('hidden');
    return;
  }
  $('#login-error').classList.add('hidden');
  openWS();
});

$('#create-room-form').addEventListener('submit', (e)=>{
  e.preventDefault();
  const r = $('#create-room-input').value.trim();
  if (!r) return;
  S.ws.send(JSON.stringify({type:'create_room', room:r}));
  $('#create-room-input').value='';
  setTimeout(()=>S.ws.send(JSON.stringify({type:'room_list'})), 200);
});

$('#leave-room').addEventListener('click', ()=>{
  S.ws.send(JSON.stringify({type:'leave_room'}));
  S.room = null;
  S.ws.send(JSON.stringify({type:'room_list'}));
  show('#screen-lobby');
});

$('#chat-form').addEventListener('submit', (e)=>{
  e.preventDefault();
  const t = $('#chat-input').value;
  if (!t) return;
  S.ws.send(JSON.stringify({type:'chat', message: t}));
  $('#chat-input').value='';
});

// Mic/Cam toggles (UI only; preview camera if ON)
async function setCam(on){
  const btn = $('#toggle-cam');
  btn.dataset.on = on ? 'true' : 'false';
  btn.textContent = on ? '📷 Cam ON' : '📷 Cam OFF';
  if (on){
    try{
      const stream = await navigator.mediaDevices.getUserMedia({video:true, audio:false});
      $('#video-preview').srcObject = stream;
    }catch(err){
      alert('Không mở được camera: ' + err.message);
    }
  }else{
    const v = $('#video-preview');
    if (v.srcObject){
      v.srcObject.getTracks().forEach(t=>t.stop());
      v.srcObject = null;
    }
  }
}
$('#toggle-cam').addEventListener('click', ()=>{
  const on = ($('#toggle-cam').dataset.on === 'true');
  setCam(!on);
});
$('#toggle-mic').addEventListener('click', ()=>{
  const btn = $('#toggle-mic');
  const on = (btn.dataset.on === 'true');
  btn.dataset.on = (!on).toString();
  btn.textContent = on ? '🎤 Mic OFF' : '🎤 Mic ON';
  // NOTE: mic streaming is not implemented in this scope
});