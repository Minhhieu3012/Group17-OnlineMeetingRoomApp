import asyncio
from protocol import send_msg, read_msg
from tcp_state import clients, rooms, Client
from routing import send_to_room, send_to_user
from file_transfer import handle_file_meta, handle_file_chunk 

async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    username = None
    try:
        while True:
            msg = await read_msg(reader)
            t = msg.get("type")
            p = msg.get("payload", {})

            # Login
            if t == "login":
                username = p["username"]
                if username in clients:
                    await send_msg(writer, {"ok": False, "error": "Username in use"})
                    continue
                clients[username] = Client(username=username, writer=writer)
                await send_msg(writer, {"ok": True, "type": "login_ok"})
                print(f"[TCP] {username} logged in from {peer}")

            # Logout
            elif t == "logout":
                await logout(username)
                break

            # Create room
            elif t == "create_room":
                r = p["room"]
                rooms.setdefault(r, set())
                await send_msg(writer, {"ok": True, "room": r})

            # Join room
            elif t == "join_room":
                r = p["room"]
                rooms.setdefault(r, set()).add(username)
                clients[username].room = r
                await send_to_room(r, {
                    "type": "system",
                    "payload": {"msg": f"{username} joined"}
                }, exclude=username)

            # Leave room
            elif t == "leave_room":
                r = clients[username].room
                if r: rooms[r].discard(username)
                clients[username].room = None

            # Chat
            elif t == "chat":
                r = clients[username].room
                if r:
                    await send_to_room(r, {
                        "type": "chat",
                        "from": username,
                        "payload": {"text": p["text"]}}
                    )

            # Direct Message
            elif t == "dm":
                await send_to_user(p["to"], {
                    "type": "dm",
                    "from": username,
                    "payload": {"text": p["text"]}}
                )

            # File transfer (gọi sang file_transfer.py)
            elif t == "file_meta":
                await handle_file_meta(username, msg, writer)

            elif t == "file_chunk":
                await handle_file_chunk(username, msg, writer)

            # UDP register
            elif t == "udp_register":
                media, port = p["media"], p["port"]
                ip = writer.get_extra_info("peername")[0]
                clients[username].udp_endpoints[media] = (ip, port)
                await send_msg(writer, {"ok": True, "registered": media})

    except Exception as e:
        print(f"[TCP] Error {peer}:", e)
    finally:
        if username: 
            await logout(username)
        writer.close()
        await writer.wait_closed()


async def logout(username):
    if username in clients:
        room = clients[username].room
        if room and username in rooms.get(room, set()):
            rooms[room].discard(username)
        clients.pop(username, None)
        print(f"[TCP] {username} logged out")


async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 5000)
    print("[TCP] Server on 5000")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
