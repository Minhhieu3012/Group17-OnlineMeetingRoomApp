from dataclasses import dataclass, field
from typing import Dict, Set, Optional  
import asyncio

@dataclass
class Client:
    username: str
    writer: asyncio.StreamWriter
    room: Optional[str] = None
    udp_endpoints: dict = field(default_factory=lambda: {"audio": None, "video": None})

# Global state
clients: Dict[str, Client] = {}
rooms: Dict[str, Set[str]] = {}
