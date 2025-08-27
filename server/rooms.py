from typing import Dict, Set, Optional

# Danh sách phòng: room_name -> set(username)
rooms: Dict[str, Set[str]] = {}

def create_room(room: str):
    """Tạo phòng mới nếu chưa tồn tại"""
    rooms.setdefault(room, set())

def join_room(username: str, room: str, clients: Dict):
    """Thêm user vào phòng"""
    create_room(room)
    rooms[room].add(username)
    clients[username].room = room

def leave_room(username: str, clients: Dict):
    """User rời khỏi phòng hiện tại"""
    room = clients[username].room
    if room and room in rooms:
        rooms[room].discard(username)
        if not rooms[room]: # nếu phòng trống thì xóa
            del rooms[room]
    clients[username].room = None

def get_user_room(username: str, clients: Dict) -> Optional[str]:
    """Lấy phòng hiện tại của user"""
    return clients[username].room if username in clients else None

def list_rooms():
    """Danh sách tất cả phòng"""
    return list(rooms.keys())

def list_users(room: str):
    """Danh sách user trong một phòng"""
    return list(rooms.get(room, []))
