# hệ thống định tuyến msg trong chat server
from tcp_state import clients, rooms
from protocol import send_msg

# Gửi trực tiếp tới 1 user
async def send_to_user(username: str, obj: dict):
    if username in clients: # kiểm tra user có onl không
        await send_msg(clients[username].writer, obj) # clients[username].writer: lấy TCP writer của user đó 

# Broadcast tới phòng
async def send_to_room(room: str, obj: dict, exclude: str = None):
    for u in rooms.get(room, set()): # lặp qua từng username trong phòng  
        if u != exclude and u in clients: # dk1: kh gửi cho người loại trừ / dk2: chỉ gửi cho user onl
            await send_msg(clients[u].writer, obj)

# Relay tin nhắn (file, chat, ...)
async def relay_message(sender: str, msg: dict):
    to = msg.get("to") # kiểm tra loại msg 
    if to:  # nếu có to là "DM"
        await send_to_user(to, msg)
    else:   # Broadcast trong phòng
        r = clients[sender].room
        if r:
            await send_to_room(r, msg, exclude=sender)
