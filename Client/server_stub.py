# filename: server_stub.py
# Purpose: Minimal in-memory TCP server (NO DATABASE) to test Huy's clients
# Protocol: 4-byte big-endian length + JSON (UTF-8), matching the client protocol
# Features:
# - auth/login with username + gmail (regex check only)
# - room:list, room:create (returns room_code), room:join (by code + optional password), room:leave
# - users:list (by room_code)
# - chat:send (broadcast to room)
# - dm:send (direct message by username)
# - file forwarding: file/meta, file/chunk, file/complete (relay to other room members)
# - presence push: {type:"presence", event:"join"|"leave", room_code, user}
#
# This is for LOCAL TEST ONLY — no persistence, restart = fresh state.

import asyncio, json, struct, re, secrets, string, time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

HOST = "127.0.0.1"
PORT = 9000

# ---------- framing helpers ----------

def pack(obj: dict) -> bytes:
    b = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return struct.pack(">I", len(b)) + b

async def recv_frame(reader: asyncio.StreamReader) -> dict:
    hdr = await reader.readexactly(4)
    (n,) = struct.unpack(">I", hdr)
    data = await reader.readexactly(n)
    return json.loads(data.decode("utf-8"))

async def send_json(writer: asyncio.StreamWriter, obj: dict):
    writer.write(pack(obj))
    await writer.drain()

# ---------- simple in-memory state ----------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@dataclass
class Client:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    username: Optional[str] = None
    gmail: Optional[str] = None
    room_code: Optional[str] = None

@dataclass
class Room:
    name: str
    password: str = ""
    owner: Optional[str] = None
    members: Set[str] = field(default_factory=set)

# transfer_id -> {room_code, from_user}
transfers: Dict[str, Dict[str, str]] = {}

# username -> Client
users: Dict[str, Client] = {}
# writer -> Client
clients_by_writer: Dict[asyncio.StreamWriter, Client] = {}
# room_code -> Room
rooms: Dict[str, Room] = {}

# ---------- helpers ----------

def gen_room_code(length: int = 4) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

async def broadcast_room(room_code: str, payload: dict, except_user: Optional[str] = None):
    room = rooms.get(room_code)
    if not room:
        return
    for uname in list(room.members):
        if except_user and uname == except_user:
            continue
        c = users.get(uname)
        if c:
            try:
                await send_json(c.writer, payload)
            except Exception:
                pass

async def push_presence(room_code: str, user: str, event: str):
    await broadcast_room(room_code, {"type": "presence", "event": event, "room_code": room_code, "user": user}, except_user=None)

async def send_error(writer: asyncio.StreamWriter, typ: str, error: str):
    await send_json(writer, {"type": typ, "status": "error", "error": error})

# ---------- handlers ----------

async def handle_auth(c: Client, msg: dict):
    action = msg.get("action")
    if action != "login":
        return await send_error(c.writer, "auth", "unsupported_action")
    username = msg.get("username", "").strip()
    gmail = msg.get("gmail", "").strip()
    if not username:
        return await send_error(c.writer, "auth", "username_required")
    if not EMAIL_RE.match(gmail):
        return await send_error(c.writer, "auth", "invalid_gmail")
    # reject duplicate username (simple policy)
    if username in users and users[username] is not c:
        return await send_error(c.writer, "auth", "username_in_use")
    # bind
    c.username, c.gmail = username, gmail
    users[username] = c
    await send_json(c.writer, {"type": "auth", "status": "ok", "user": username})

async def handle_room(c: Client, msg: dict):
    action = msg.get("action")
    if action == "list":
        data = []
        for code, r in rooms.items():
            data.append({"name": r.name, "code": code, "count": len(r.members)})
        return await send_json(c.writer, {"type": "room", "rooms": data})

    if action == "create":
        name = (msg.get("room_name") or "Room").strip() or "Room"
        pwd = msg.get("password", "")
        code = gen_room_code()
        rooms[code] = Room(name=name, password=pwd, owner=c.username or None)
        return await send_json(c.writer, {"type": "room", "status": "ok", "room_id": f"R-{code}", "room_code": code, "owner": c.username})

    if action == "join":
        code = msg.get("room_code", "").strip().upper()
        pwd = msg.get("password", "")
        r = rooms.get(code)
        if not r:
            return await send_error(c.writer, "room", "invalid_code_or_password")
        if r.password and r.password != pwd:
            return await send_error(c.writer, "room", "invalid_code_or_password")
        # leave current room first
        if c.room_code and c.room_code in rooms:
            old = rooms[c.room_code]
            if c.username in old.members:
                old.members.remove(c.username)  # type: ignore
                await push_presence(c.room_code, c.username, "leave")
        # join new
        r.members.add(c.username)  # type: ignore
        c.room_code = code
        await send_json(c.writer, {"type": "room", "status": "ok", "room_id": f"R-{code}", "room_code": code})
        await push_presence(code, c.username, "join")
        return

    if action == "leave":
        if c.room_code and c.room_code in rooms and c.username in rooms[c.room_code].members:
            rooms[c.room_code].members.remove(c.username)  # type: ignore
            await push_presence(c.room_code, c.username, "leave")
        c.room_code = None
        return await send_json(c.writer, {"type": "room", "status": "ok", "left": True})

    await send_error(c.writer, "room", "unsupported_action")

async def handle_users(c: Client, msg: dict):
    code = (msg.get("room_code") or c.room_code or "").strip().upper()
    if not code or code not in rooms:
        return await send_error(c.writer, "users", "unknown_room")
    r = rooms[code]
    data = sorted(list(r.members))
    await send_json(c.writer, {"type": "users", "room_code": code, "users": data})

async def handle_chat(c: Client, msg: dict):
    action = msg.get("action")
    if action != "send":
        return await send_error(c.writer, "chat", "unsupported_action")
    code = (msg.get("room_code") or c.room_code or "").strip().upper()
    if not code or code not in rooms:
        return await send_error(c.writer, "chat", "not_in_room")
    text = str(msg.get("text", ""))
    payload = {"type": "chat", "room_code": code, "from": c.username, "text": text, "ts": int(time.time())}
    await broadcast_room(code, payload, except_user=None)

async def handle_dm(c: Client, msg: dict):
    action = msg.get("action")
    if action != "send":
        return await send_error(c.writer, "dm", "unsupported_action")
    to_user = (msg.get("to") or "").strip()
    if not to_user or to_user not in users:
        return await send_error(c.writer, "dm", "user_not_found")
    text = str(msg.get("text", ""))
    payload = {"type": "dm", "from": c.username, "to": to_user, "text": text, "ts": int(time.time())}
    # send to recipient
    try:
        await send_json(users[to_user].writer, payload)
    except Exception:
        pass
    # echo back to sender (useful UX)
    try:
        await send_json(c.writer, payload)
    except Exception:
        pass

async def handle_file(c: Client, msg: dict):
    action = msg.get("action")
    if action == "meta":
        code = (msg.get("room_code") or c.room_code or "").strip().upper()
        if not code or code not in rooms:
            return await send_error(c.writer, "file", "not_in_room")
        tid = msg.get("transfer_id")
        if not tid:
            return await send_error(c.writer, "file", "missing_transfer_id")
        transfers[tid] = {"room_code": code, "from_user": c.username or ""}
        # forward to others
        await broadcast_room(code, msg, except_user=c.username)
        return
    elif action in ("chunk", "complete"):
        tid = msg.get("transfer_id")
        info = transfers.get(tid)
        if not info:
            return  # silently drop unknown transfer
        code = info["room_code"]
        await broadcast_room(code, msg, except_user=c.username)
        if action == "complete":
            transfers.pop(tid, None)
        return
    else:
        return await send_error(c.writer, "file", "unsupported_action")

# ---------- client loop ----------

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    c = Client(reader=reader, writer=writer)
    clients_by_writer[writer] = c
    addr = writer.get_extra_info("peername")
    print(f"[+] connection from {addr}")
    try:
        while True:
            msg = await recv_frame(reader)
            if isinstance(msg, dict) and msg.get("enc"):
                # Encryption not supported in stub; you can add AES here if needed
                await send_error(writer, "auth", "encrypted_messages_not_supported_in_stub")
                continue
            typ = msg.get("type")
            if typ == "auth":
                await handle_auth(c, msg)
            elif typ == "room":
                await handle_room(c, msg)
            elif typ == "users":
                await handle_users(c, msg)
            elif typ == "chat":
                await handle_chat(c, msg)
            elif typ == "dm":
                await handle_dm(c, msg)
            elif typ == "file":
                await handle_file(c, msg)
            else:
                await send_error(writer, "generic", f"unknown_type:{typ}")
    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        print("[!] client error:", e)
    finally:
        # cleanup
        try:
            if c.username:
                # leave room if in one
                if c.room_code and c.room_code in rooms and c.username in rooms[c.room_code].members:
                    rooms[c.room_code].members.remove(c.username)
                    await push_presence(c.room_code, c.username, "leave")
                users.pop(c.username, None)
        except Exception:
            pass
        clients_by_writer.pop(writer, None)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        print(f"[-] disconnected {addr}")

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addr = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"TCP server listening on {addr}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
