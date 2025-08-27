# tcp_server.py
import asyncio, base64
from protocol import send_msg, read_msg, send_msg_secure, read_msg_secure, read_any, send_any
from tcp_state import clients, rooms, Client
from routing import send_to_room, send_to_user
from file_transfer import handle_file_meta, handle_file_chunk
from auth import authenticate_user, create_session, end_session, get_session_key, touch_session

async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    username = None
    aes_key = None  # khóa phiên để mã hóa sau login

    try:
        # --- Vòng lặp nhận/gửi ---
        while True:
            # Trước login: đọc thường; sau login: đọc secure
            msg = await read_any(reader, aes_key)
            t  = msg.get("type")
            p  = msg.get("payload", {})

            # ===== LOGIN =====
            if t == "login":
                username = p.get("username")
                password = p.get("password", "")
                if not username:
                    await send_msg(writer, {"ok": False, "error": "Missing username"})
                    continue

                # reject nếu đang online
                if username in clients:
                    await send_msg(writer, {"ok": False, "error": "Username in use"})
                    continue

                # xác thực qua auth.py
                if not authenticate_user(username, password):
                    await send_msg(writer, {"ok": False, "error": "Invalid credentials"})
                    continue

                # tạo session + khóa phiên
                token, key = create_session(username)
                aes_key = key  # từ bây giờ, server kỳ vọng client dùng secure

                # đăng ký client
                clients[username] = Client(username=username, writer=writer)

                # gửi login_ok + token + khóa (base64) cho client
                await send_msg(writer, {
                    "ok": True,
                    "type": "login_ok",
                    "token": token,
                    "aes_key_b64": base64.b64encode(key).decode()
                })
                print(f"[TCP] {username} logged in from {peer}")

            # ===== LOGOUT =====
            elif t == "logout":
                break  # ra finally để cleanup

            # ===== ROOMS =====
            elif t == "create_room":
                r = p["room"]
                rooms.setdefault(r, set())
                await send_any(writer, {"ok": True, "room": r}, aes_key)

            elif t == "join_room":
                r = p["room"]
                rooms.setdefault(r, set()).add(username)
                clients[username].room = r
                await send_to_room(r, {
                    "type": "system",
                    "payload": {"msg": f"{username} joined"}
                }, exclude=username)

            elif t == "leave_room":
                r = clients[username].room
                if r: rooms[r].discard(username)
                clients[username].room = None

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
                await handle_file_meta(username, msg, writer)   # bản thân tin này có thể secure/không tuỳ bạn
            elif t == "file_chunk":
                await handle_file_chunk(username, msg, writer)

            # ===== UDP REGISTER =====
            elif t == "udp_register":
                media, port = p["media"], p["port"]
                ip = writer.get_extra_info("peername")[0]
                clients[username].udp_endpoints[media] = (ip, port)
                await send_any(writer, {"ok": True, "registered": media}, aes_key)

            # touch session (activity)
            if username:
                touch_session(username)

    except Exception as e:
        print(f"[TCP] Error {peer}:", e)
    finally:
        if username:
            # rời phòng + xóa client + hủy session
            r = clients.get(username, Client(username, writer)).room
            if r and username in rooms.get(r, set()):
                rooms[r].discard(username)
            clients.pop(username, None)
            end_session(username)
            print(f"[TCP] {username} logged out")

        writer.close()
        await writer.wait_closed()

async def main():
    # ---- Bật TLS (tùy chọn) ----
    # import ssl
    # ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # ssl_ctx.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
    # server = await asyncio.start_server(handle_client, "0.0.0.0", 5000, ssl=ssl_ctx)

    # Không dùng TLS:
    server = await asyncio.start_server(handle_client, "0.0.0.0", 5000)
    print("[TCP] Server on 5000")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
