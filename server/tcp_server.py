import asyncio, base64
from .protocol import send_msg, read_msg, send_msg_secure, read_msg_secure, read_any, send_any
from .tcp_state import clients, rooms, Client
from .routing import send_to_room, send_to_user
from .file_transfer import handle_file_meta, handle_file_chunk
from .auth import authenticate_user, create_session, end_session, get_session_key, touch_session, register_user

async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    username = None
    aes_key = None

    try:
        while True:
            msg = await read_any(reader, aes_key)
            t = msg.get("type")
            p = msg.get("payload", {})

            # ===== LOGIN =====
            if t == "login":
                username = p.get("username")
                password = p.get("password", "")
                if not username:
                    await send_msg(writer, {"ok": False, "type": "error", "error": "Missing username"})
                    continue

                if username == "_gateway_" and password == "gateway_internal_auth_2024":
                    await send_msg(writer, {"ok": True, "type": "gateway_auth_ok"})
                    print(f"[TCP] Gateway authenticated from {peer}")
                    username = "_gateway_"
                    continue

                if username in clients:
                    await send_msg(writer, {"ok": False, "type": "error", "error": "Username in use"})
                    continue

                if not authenticate_user(username, password):
                    await send_msg(writer, {"ok": False, "type": "error", "error": "Invalid credentials"})
                    continue

                token, key = create_session(username)
                aes_key = key

                clients[username] = Client(username=username, writer=writer)

                await send_msg(writer, {
                    "ok": True,
                    "type": "login_ok",
                    "token": token,
                    "aes_key_b64": base64.b64encode(key).decode()
                })
                print(f"[TCP] {username} logged in from {peer}")

            # ===== REGISTER =====
            elif t == "register":
                username = p.get("username")
                email = p.get("email")
                password = p.get("password", "")
                
                if not username or not email or not password:
                    await send_msg(writer, {"ok": False, "type": "error", "error": "Missing required fields"})
                    continue

                if username in clients:
                    await send_msg(writer, {"ok": False, "type": "error", "error": "Username already in use"})
                    continue

                success, error = register_user(username, email, password)
                
                if not success:
                    await send_msg(writer, {"ok": False, "type": "error", "error": error})
                    continue

                token, key = create_session(username)
                aes_key = key

                clients[username] = Client(username=username, writer=writer)

                await send_msg(writer, {
                    "ok": True,
                    "type": "register_ok",
                    "token": token,
                    "aes_key_b64": base64.b64encode(key).decode()
                })
                print(f"[TCP] {username} registered and logged in from {peer}")

            # ===== LOGOUT =====
            elif t == "logout":
                break

            # ===== ROOMS =====
            elif t == "create_room":
                r = p["room"]
                rooms.setdefault(r, set())
                await send_any(writer, {"ok": True, "type": "create_room_ok", "room": r}, aes_key)

            elif t == "join_room":
                r = p["room"]
                rooms.setdefault(r, set()).add(username)
                clients[username].room = r
                await send_to_room(r, {
                    "type": "system",
                    "payload": {"msg": f"{username} joined"}
                }, exclude=username)
                await send_any(writer, {"ok": True, "type": "join_room_ok", "room": r}, aes_key)

            elif t == "leave_room":
                r = clients[username].room
                if r: rooms[r].discard(username)
                clients[username].room = None
                await send_any(writer, {"ok": True, "type": "leave_room_ok", "room": r}, aes_key)

            elif t == "list_rooms":
                room_list = [{"name": room, "users": len(users)} for room, users in rooms.items()]
                await send_any(writer, {"ok": True, "type": "rooms", "rooms": room_list}, aes_key)

            # ===== CHAT / DM =====
            elif t == "chat":
                r = clients[username].room
                if r:
                    await send_to_room(r, {
                        "type": "chat", "from": username,
                        "payload": {"text": p["text"]}
                    })

            elif t == "dm":
                await send_to_user(p["to"], {
                    "type": "dm", "from": username,
                    "payload": {"text": p["text"]}
                })

            # ===== FILE TRANSFER =====
            elif t == "file_meta":
                await handle_file_meta(username, msg, writer)
            elif t == "file_chunk":
                await handle_file_chunk(username, msg, writer)

            # ===== UDP REGISTER =====
            elif t == "udp_register":
                media, port = p["media"], p["port"]
                ip = writer.get_extra_info("peername")[0]
                clients[username].udp_endpoints[media] = (ip, port)
                await send_any(writer, {"ok": True, "type": "udp_register_ok", "registered": media}, aes_key)

            if username:
                touch_session(username)

    except Exception as e:
        print(f"[TCP] Error {peer}:", e)
    finally:
        if username:
            r = clients.get(username, Client(username, writer)).room
            if r and username in rooms.get(r, set()):
                rooms[r].discard(username)
            clients.pop(username, None)
            end_session(username)
            print(f"[TCP] {username} logged out")

        writer.close()
        await writer.wait_closed()

async def main(host="0.0.0.0", port=8888):
    server = await asyncio.start_server(handle_client, host, port)
    print(f"[TCP] Server on {host}:{port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    from advanced_feature import config
    asyncio.run(main(config.SERVER_HOST, config.TCP_PORT))
