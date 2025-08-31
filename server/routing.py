from .tcp_state import clients, rooms
from .protocol import send_msg

# Gửi trực tiếp tới 1 user
async def send_to_user(username: str, obj: dict):
    if username in clients:
        await send_msg(clients[username].writer, obj)

# Broadcast tới phòng
async def send_to_room(room: str, obj: dict, exclude: str = None):
    for u in rooms.get(room, set()):
        if u != exclude and u in clients:
            await send_msg(clients[u].writer, obj)

# Relay tin nhắn (file, chat, ...)
async def relay_message(sender: str, msg: dict):
    to = msg.get("to")
    if to:  # DM
        await send_to_user(to, msg)
    else:   # Broadcast trong phòng
        r = clients[sender].room
        if r:
            await send_to_room(r, msg, exclude=sender)
