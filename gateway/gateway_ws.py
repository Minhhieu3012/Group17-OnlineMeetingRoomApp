import asyncio
import base64
import json
import logging
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

# Reuse server protocol helpers for wire-format compatibility
from server.protocol import (
    send_msg as tcp_send_plain,
    read_msg as tcp_read_plain,
    send_msg_secure as tcp_send_secure,
    read_msg_secure as tcp_read_secure,
)


logger = logging.getLogger("GatewayWS")
logger.setLevel(logging.INFO)


class Gateway:
    """
    WebSocket → TCP gateway.

    - Browser/web client speaks JSON text frames (UTF-8).
    - Gateway forwards to TCP server using the same length‑prefixed protocol
      (plain JSON before login; AES-GCM after login using `aes_key_b64` the
      TCP server returns in `login_ok`).
    - TCP responses are decrypted (if needed) and forwarded back to WS as JSON
      text.
    """

    def __init__(self, tcp_host: str = "127.0.0.1", tcp_port: int = 8888, web_port: int = 8765,
                 host: str = "0.0.0.0") -> None:
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.web_port = web_port
        self.host = host
        self._server: Optional[websockets.server.Serve] = None

    async def _handle_ws(self, ws: WebSocketServerProtocol):
        peer = f"{ws.remote_address[0]}:{ws.remote_address[1]}" if ws.remote_address else "?"
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        try:
            reader, writer = await asyncio.open_connection(self.tcp_host, self.tcp_port)
        except Exception as e:  # TCP connect failed
            logger.error("TCP connect error from %s: %s", peer, e)
            await ws.close(code=1011, reason="TCP upstream unavailable")
            return

        aes_key: Optional[bytes] = None
        closed = False

        async def ws_to_tcp():
            nonlocal aes_key
            async for text in ws:
                try:
                    obj = json.loads(text)
                except Exception:
                    await ws.send(json.dumps({"ok": False, "type": "error", "error": "Invalid JSON"}))
                    continue
                # Before login we must talk in plaintext; after login we encrypt
                t = obj.get("type")
                try:
                    if t == "login" or aes_key is None:
                        await tcp_send_plain(writer, obj)
                    else:
                        await tcp_send_secure(writer, obj, aes_key)
                except Exception as e:
                    logger.error("Upstream send failed: %s", e)
                    await ws.close(code=1011, reason="Upstream error")
                    break

        async def tcp_to_ws():
            nonlocal aes_key
            while True:
                try:
                    if aes_key is None:
                        msg = await tcp_read_plain(reader)
                    else:
                        msg = await tcp_read_secure(reader, aes_key)
                except asyncio.IncompleteReadError:
                    logger.info("TCP closed by upstream")
                    await ws.close(code=1011, reason="Upstream closed")
                    break
                except Exception as e:
                    logger.error("Error reading from upstream: %s", e)
                    await ws.close(code=1011, reason="Upstream error")
                    break

                # Capture AES key after login_ok
                if isinstance(msg, dict) and msg.get("type") == "login_ok":
                    k = msg.get("aes_key_b64")
                    if k:
                        try:
                            aes_key = base64.b64decode(k)
                        except Exception:
                            logger.warning("Invalid AES key from upstream")
                            aes_key = None

                try:
                    await ws.send(json.dumps(msg))
                except Exception:
                    break

        try:
            await asyncio.gather(ws_to_tcp(), tcp_to_ws())
        finally:
            if not closed:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def start(self):
        logger.info("Starting WebSocket Gateway on %s:%s → TCP %s:%s", self.host, self.web_port, self.tcp_host, self.tcp_port)
        async with websockets.serve(self._handle_ws, self.host, self.web_port, ping_interval=20, ping_timeout=20, max_size=2**20):
            await asyncio.Future()  # run forever
