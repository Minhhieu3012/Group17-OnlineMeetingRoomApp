from collections import defaultdict
import logging

logger=logging.getLongger(__name__)

# lưu trữ các phòng 
rooms=defaultdict(set) # room_name -> set of usernames
user_rooms={} # username -> room_name

def join_room(username:str, room:str) -> None:
    # Neu user dang o phong khac -> roi khoi 
    if username in user_rooms:
        old_room=user_rooms[username]
        if old_room==room:
            rooms[old_room].discard(username)
            logger.info(f"{username} roi khoi {old_room}")

            # Neu phong cu trong -> xoa
            if not rooms[old_room]:
                del rooms[old_room]
    
    # Them user vao phong moi
    rooms[room].add(username)
    user_rooms[username]=room
    logger.info(f"{username} tham gia {room}")