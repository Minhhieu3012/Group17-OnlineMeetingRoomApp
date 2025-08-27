import asyncio, json, struct
from dataclasses import dataclass, field
from typing import Dict, Set, Optional

# -------- STATE (lưu trữ trạng thái) --------
@dataclass
class Client:
    username: str # tên người dùng 
    writer: asyncio.StreamWriter # kết nối tcp để gửi dữ liệu
    room: Optional[str] = None # phòng chat hiện tại (có thể None)
    udp_endpoints: dict = field(default_factory=lambda: {"audio": None, "video": None}) # endpoint UDP để nhận media

clients: Dict[str, Client] = {} # username -> Client object
rooms: Dict[str, Set[str]] = {}  # room_name -> set of usernames    

# -------- PROTOCOL (cách giao tiếp) --------
async def send_msg(writer, obj: dict):
    data = json.dumps(obj).encode() # chuyển dict thành json string, rồi thành bytes
    writer.write(struct.pack("!I", len(data)) + data) # gửi [4 bytes big-endian độ dài][nội dung]
    await writer.drain() # đảm bảo dữ liệu được gửi đi 

async def read_msg(reader: asyncio.StreamReader):
    header = await reader.readexactly(4) # đọc đúng 4 bytes
    (ln,) = struct.unpack("!I", header) # unpack để lấy độ dài nội dung
    data = await reader.readexactly(ln) # đọc đúng 'ln' bytes nội dung
    return json.loads(data.decode()) # chuyển bytes thành json string, rồi thành dict

# -------- HANDLER --------
async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername") # lấy IP:port của client, peername là tuple (ip,port)
    username = None
    try: 
        while True: # lặp để xử lý nhiều tin nhắn từ client
            msg = await read_msg(reader)
            t = msg.get("type") # loại tin nhắn
            p = msg.get("payload", {}) # nội dung tin nhắn

            #Login
            if t == "login":
                username = p["username"]
                if username in clients: # kiểm tra xem username đã tồn tại chưa
                    await send_msg(writer, {"ok": False, "error": "Username already in use"})
                    continue # yêu cầu client gửi lại username khác
                clients[username] = Client(username=username, writer=writer) # lưu trữ thông tin client
                await send_msg(writer, {"ok": True, "type":"login_ok"})
                print(f"[TCP] {username} logged in from {peer}")

            #Logout
            elif t == "logout":
                await logout(username) # gọi hàm logout
                break # thoát vòng lặp, đóng kết nối
            
            #Create room
            elif t == "create_room":
                r = p["room"] # tên phòng
                rooms.setdefault(r, set()) # tạo phòng nếu chưa tồn tại
                await send_msg(writer, {"ok": True, "room": r})
           
            #Join room
            elif t == "join_room":
                r = p["room"]
                rooms.setdefault(r, set()).add(username) # thêm user vào phòng
                clients[username].room = r # lưu trạng thái user đang ở phòng nào
                await broadcast(r, {"type":"system","payload":{"msg":f"{username} joined"}}, exclude=username) # thông báo cho mọi người trong phòng (trừ user này)

            #Leave room
            elif t == "leave_room":
                r = clients[username].room # lấy phòng hiện tại của user
                if r: rooms[r].discard(username) # xóa user khỏi phòng
                clients[username].room = None

            #Chat (tin nhắn trong phòng)
            elif t == "chat":
                r = clients[username].room
                if r: # nếu user đang ở trong phòng
                    await broadcast(r, {"type":"chat","from":username,"payload":{"text":p["text"]}}, exclude=None) # gửi tin nhắn cho mọi người trong phòng

            #Direct message
            elif t == "dm":
                to = p["to"] # username của người nhận
                if to in clients: # kiểm tra người nhận có online không
                    await send_msg(clients[to].writer, {"type":"dm","from":username,"payload":{"text":p["text"]}})
                else:
                    await send_msg(writer, {"ok": False, "error":"User offline"})

            #File transfer
            elif t == "file_meta": # gửi thông tin file trước khi gửi dữ liệu file
                if p["size"] > 20_000_000: # giới hạn file 20MB
                    await send_msg(writer, {"ok": False, "error":"File too large"})
                else:
                    await relay_room_or_to(username, msg) # chuyển tiếp metadata file

            elif t == "file_chunk": # gửi dữ liệu file theo từng chunk
                if len(p["data"]) > 1_500_000: # giới hạn chunk 1.5MB
                    await send_msg(writer, {"ok": False, "error":"Chunk too large"})
                else:
                    await relay_room_or_to(username, msg) # chuyển tiếp chunk file

            #UDP registration (đăng ký endpoint UDP để nhận media như voice/video call)
            elif t == "udp_register":
                media, port = p["media"], p["port"] # media = "audio" hoặc "video"
                ip = writer.get_extra_info("peername")[0] # lấy IP của client
                clients[username].udp_endpoints[media] = (ip, port) # lưu endpoint UDP
                await send_msg(writer, {"ok": True, "registered": media})

    except Exception as e:
        print(f"[TCP] Error {peer}:", e)
    finally:
        if username: await logout(username) # đảm bảo logout khi kết nối đóng
        writer.close()
        await writer.wait_closed()

# -------- HELPERS --------
async def logout(username):
    if username in clients:
        room = clients[username].room # lấy phòng hiện tại của user
        if room and username in rooms.get(room, set()):
            rooms[room].discard(username) # xóa user khỏi phòng
        clients.pop(username, None) # xóa user khỏi danh sách clients
        print(f"[TCP] {username} logged out")

async def broadcast(room, obj, exclude=None):
    for u in rooms.get(room, set()): # lặp qua tất cả user trong phòng
        if u == exclude: continue # bỏ qua user cần loại trừ
        await send_msg(clients[u].writer, obj) # gửi tin nhắn đến user

async def relay_room_or_to(sender, msg):
    to = msg.get("to") # Kiểm tra có gửi tin nhắn riêng không
    if to and to in clients: # gửi tin nhắn riêng
        await send_msg(clients[to].writer, msg)
    else: # gửi tin nhắn trong phòng
        r = clients[sender].room
        if r: await broadcast(r, msg, exclude=sender)

# -------- MAIN --------
async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 5000)
    print("[TCP] Server on 5000")
    async with server: # đóng server khi thoát khỏi block
        await server.serve_forever() # chạy server mãi mãi

if __name__ == "__main__":
    asyncio.run(main())