from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Room:
    """Phòng họp: owner có quyền kick, members chứa danh sách user trong phòng."""

    room_id: str
    owner: str
    members: Set[str] = field(default_factory=set)
    topic: Optional[str] = None

    def add_member(self, username: str) -> None:
        self.members.add(username)

    def remove_member(self, username: str) -> None:
        self.members.discard(username)

    def is_member(self, username: str) -> bool:
        return username in self.members

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "owner": self.owner,
            "members": sorted(self.members),
            "topic": self.topic,
        }


class RoomManager:
    """Quản lý nhiều phòng cho server TCP/UDP.

    Hỗ trợ: tạo/join/leave/kick, truy vấn danh sách phòng.
    """

    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._user_to_room: Dict[str, str] = {}
        self._lock = threading.Lock()

    # ---------- Queries ----------
    def list_rooms(self) -> List[dict]:
        with self._lock:
            return [room.to_dict() for room in self._rooms.values()]

    def get_room(self, room_id: str) -> Optional[Room]:
        with self._lock:
            return self._rooms.get(room_id)

    def get_room_info(self, room_id: str) -> Optional[dict]:
        with self._lock:
            room = self._rooms.get(room_id)
            return room.to_dict() if room else None

    def get_user_room(self, username: str) -> Optional[str]:
        with self._lock:
            return self._user_to_room.get(username)

    # ---------- Mutations ----------
    def create_room(self, room_id: str, owner: str, topic: Optional[str] = None) -> Room:
        with self._lock:
            if room_id in self._rooms:
                raise ValueError("Room đã tồn tại")
            room = Room(room_id=room_id, owner=owner, topic=topic)
            room.add_member(owner)
            self._rooms[room_id] = room
            self._user_to_room[owner] = room_id
            return room

    def delete_room_if_empty(self, room_id: str) -> None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room and not room.members:
                del self._rooms[room_id]

    def join_room(self, room_id: str, username: str) -> Room:
        with self._lock:
            # Nếu user đang ở phòng khác, rời phòng cũ trước
            cur = self._user_to_room.get(username)
            if cur and cur != room_id:
                old = self._rooms.get(cur)
                if old:
                    old.remove_member(username)
                    if not old.members:
                        del self._rooms[cur]
                del self._user_to_room[username]

            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError("Room không tồn tại")
            room.add_member(username)
            self._user_to_room[username] = room_id
            return room

    def leave_room(self, username: str) -> Optional[str]:
        """User rời phòng. Trả về room_id nếu có, None nếu user chưa ở phòng nào."""
        with self._lock:
            room_id = self._user_to_room.pop(username, None)
            if not room_id:
                return None
            room = self._rooms.get(room_id)
            if room:
                room.remove_member(username)
                # Nếu owner rời phòng, chuyển owner cho người đầu tiên còn lại (nếu có)
                if username == room.owner and room.members:
                    room.owner = next(iter(room.members))
                if not room.members:
                    del self._rooms[room_id]
            return room_id

    def kick_user(self, room_id: str, owner: str, target: str) -> None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                raise ValueError("Room không tồn tại")
            if room.owner != owner:
                raise PermissionError("Chỉ owner mới có quyền kick")
            if target not in room.members:
                raise ValueError("User không ở trong phòng")
            if target == owner:
                raise ValueError("Owner không thể tự kick mình")
            room.remove_member(target)
            self._user_to_room.pop(target, None)
            if not room.members:
                del self._rooms[room_id]
