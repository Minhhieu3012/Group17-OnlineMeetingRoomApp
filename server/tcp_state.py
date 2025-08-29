# define ctdl của server
from dataclasses import dataclass, field # field: customize behavior cho từng field
from typing import Dict, Set, Optional  
import asyncio

@dataclass
class Client:
    username: str
    writer: asyncio.StreamWriter
    room: Optional[str] = None # = None là default value - user chưa vào phòng nào 
    udp_endpoints: dict = field(default_factory=lambda: {"audio": None, "video": None})

# Global state
clients: Dict[str, Client] = {}      # username -> Client
rooms: Dict[str, Set[str]] = {}      # room_name -> set of usernames
