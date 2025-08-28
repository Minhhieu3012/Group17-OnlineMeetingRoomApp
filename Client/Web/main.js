let ws = null;
let currentRoomCode = null;

const el = (id) => document.getElementById(id);
const log = (s) => { el('log').textContent += s + "\n"; el('log').scrollTop = el('log').scrollHeight; }

function send(obj){
  if(ws && ws.readyState===WebSocket.OPEN){ ws.send(JSON.stringify(obj)); }
}

function renderRooms(rooms){
  const ul = el('rooms'); ul.innerHTML = '';
  rooms.forEach(r => {
    const li = document.createElement('li');
    li.textContent = `${r.name} (${r.count ?? '?'}) code=${r.code ?? '?'}`;
    li.onclick = () => { currentRoomCode = r.code; send({type:'room', action:'join', room_code:r.code, password:''}); send({type:'users', action:'list', room_code:r.code}); }
    ul.appendChild(li);
  });
}

function renderUsers(users){
  const ul = el('users'); ul.innerHTML = '';
  users.forEach(u => { const li = document.createElement('li'); li.textContent = u; ul.appendChild(li); });
}

function handleMessage(e){
  const msg = JSON.parse(e.data);
  if(msg.type==='room' && msg.rooms){ renderRooms(msg.rooms); }
  else if(msg.type==='users'){ renderUsers(msg.users || []); }
  else if(msg.type==='presence'){ log(`[presence] ${msg.user} ${msg.event} ${msg.room_code}`); send({type:'users', action:'list', room_code: msg.room_code}); }
  else if(msg.type==='chat'){ log(`[${msg.room_code}] ${msg.from}: ${msg.text}`); }
  else if(msg.type==='dm'){ log(`[DM] ${msg.from} → ${msg.to}: ${msg.text}`); }
  else if(msg.type==='auth' && msg.status==='ok'){ log(`[i] Login OK as ${msg.user}`); send({type:'room', action:'list'}); }
  else if(msg.type==='auth' && msg.status==='error'){ log(`[!] Login failed: ${msg.error}`); }
}

function connect(){
  const url = el('host').value.trim();
  ws = new WebSocket(url);
  ws.onopen = () => {
    log('[i] Connected to gateway');
    const u = el('user').value.trim();
    const g = el('gmail').value.trim();
    send({type:'auth', action:'login', username:u, gmail:g});
  };
  ws.onmessage = handleMessage;
  ws.onclose = () => log('[i] Disconnected');
}

el('btnConnect').onclick = connect;
el('btnListRooms').onclick = () => send({type:'room', action:'list'});
el('btnCreate').onclick = () => {
  const name = el('roomName').value.trim();
  const pwd = el('roomPwd').value;
  send({type:'room', action:'create', room_name:name, password:pwd});
};
el('btnJoinCode').onclick = () => {
  const code = el('roomCode').value.trim();
  const pwd = el('joinPwd').value;
  currentRoomCode = code;
  send({type:'room', action:'join', room_code:code, password:pwd});
  send({type:'users', action:'list', room_code:code});
};
el('btnSend').onclick = () => {
  const text = el('msg').value.trim(); if(!text) return;
  if(!currentRoomCode){ log('[!] Join a room first'); return; }
  send({type:'chat', action:'send', room_code: currentRoomCode, text});
  el('msg').value='';
};
