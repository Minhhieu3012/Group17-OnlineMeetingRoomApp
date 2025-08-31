from .tcp_state import clients, rooms
from .protocol import send_any

# Gửi trực tiếp tới 1 user
async def send_to_user(username: str, obj: dict):
    if username in clients:
        client = clients[username]
        print(f"[DEBUG][ROUTING] send_to_user → {username}: {obj}")
        await send_any(client.writer, obj, getattr(client, "aes_key", None))

# Broadcast tới phòng
async def send_to_room(room: str, obj: dict, exclude: str = None):
    print(f"[DEBUG][ROUTING] broadcast room={room}, exclude={exclude}, obj={obj}")
    for u in rooms.get(room, set()):
        if u != exclude and u in clients:
            client = clients[u]
            print(f"[DEBUG][ROUTING]  → to {u}")
            await send_any(client.writer, obj, getattr(client, "aes_key", None))

# Relay tin nhắn (file, chat, ...)
async def relay_message(sender: str, msg: dict):
    to = msg.get("to")
    if to:  # DM
        print(f"[DEBUG][ROUTING] relay DM from={sender} to={to} msg={msg}")
        await send_to_user(to, msg)
    else:   # Broadcast trong phòng
        r = clients[sender].room
        if r:
            print(f"[DEBUG][ROUTING] relay broadcast from={sender} room={r} msg={msg}")
            await send_to_room(r, msg, exclude=sender)
