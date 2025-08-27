import asyncio, json, struct
from dataclasses import dataclass, field
from typing import Dict, Optional
import rooms   # import module quản lý phòng

@dataclass
class Client:
    username: str
    writer: asyncio.StreamWriter
    room: Optional[str] = None
    udp_endpoints: dict = field(default_factory=lambda: {"audio": None, "video": None})

clients: Dict[str, Client] = {}

# ====== Helper ======
async def send_msg(writer, obj: dict):
    data = json.dumps(obj).encode()
    writer.write(struct.pack("!I", len(data)) + data)
    await writer.drain()

async def read_msg(reader: asyncio.StreamReader):
    header = await reader.readexactly(4)
    (ln,) = struct.unpack("!I", header)
    data = await reader.readexactly(ln)
    return json.loads(data.decode())

# ====== Handler ======
async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    username = None
    try:
        while True:
            msg = await read_msg(reader)
            t = msg.get("type")
            p = msg.get("payload", {})

            if t == "login":
                username = p["username"]
                if username in clients:
                    await send_msg(writer, {"ok": False, "error": "Username already in use"})
                    continue
                clients[username] = Client(username=username, writer=writer)
                await send_msg(writer, {"ok": True, "type": "login_ok"})
                print(f"[TCP] {username} logged in from {peer}")

            elif t == "logout":
                await logout(username)
                break

            elif t == "create_room":
                r = p["room"]
                rooms.create_room(r)
                await send_msg(writer, {"ok": True, "room": r})

            elif t == "join_room":
                r = p["room"]
                rooms.join_room(username, r, clients)
                await broadcast(r, {"type":"system","payload":{"msg":f"{username} joined"}}, exclude=username)

            elif t == "leave_room":
                rooms.leave_room(username, clients)

            elif t == "chat":
                r = rooms.get_user_room(username, clients)
                if r:
                    await broadcast(r, {"type":"chat","from":username,"payload":{"text":p["text"]}})

            elif t == "dm":
                to = p["to"]
                if to in clients:
                    await send_msg(clients[to].writer, {"type":"dm","from":username,"payload":{"text":p["text"]}})
                else:
                    await send_msg(writer, {"ok": False, "error": "User offline"})

            # File transfer
            elif t in ("file_meta", "file_chunk"):
                await relay_room_or_to(username, msg)

            elif t == "udp_register":
                media, port = p["media"], p["port"]
                ip = writer.get_extra_info("peername")[0]
                clients[username].udp_endpoints[media] = (ip, port)
                await send_msg(writer, {"ok": True, "registered": media})

    except Exception as e:
        print(f"[TCP] Error {peer}: {e}")
    finally:
        if username: await logout(username)
        writer.close()
        await writer.wait_closed()

# ====== Helpers ======
async def logout(username):
    if username in clients:
        rooms.leave_room(username, clients)
        clients.pop(username, None)
        print(f"[TCP] {username} logged out")

async def broadcast(room, obj, exclude=None):
    for u in rooms.rooms.get(room, set()):
        if u == exclude: continue
        await send_msg(clients[u].writer, obj)

async def relay_room_or_to(sender, msg):
    to = msg.get("to")
    if to and to in clients:
        await send_msg(clients[to].writer, msg)
    else:
        r = rooms.get_user_room(sender, clients)
        if r: await broadcast(r, msg, exclude=sender)

# ====== Main ======
async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 5000)
    print("[TCP] Server on 5000")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
