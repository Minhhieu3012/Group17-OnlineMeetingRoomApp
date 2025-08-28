# filename: ws_gateway.py
import asyncio, json, struct
import websockets

# TCP framing helpers
def pack(obj: dict) -> bytes:
    b = json.dumps(obj, separators=(",", ":")).encode()
    return struct.pack(">I", len(b)) + b

async def recv_frame(reader: asyncio.StreamReader):
    hdr = await reader.readexactly(4)
    (n,) = struct.unpack(">I", hdr)
    data = await reader.readexactly(n)
    return json.loads(data.decode())

async def proxy_connection(websocket, path, tcp_host="127.0.0.1", tcp_port=9000):
    reader, writer = await asyncio.open_connection(tcp_host, tcp_port)

    async def from_ws_to_tcp():
        async for message in websocket:
            if isinstance(message, (bytes, bytearray)):
                continue
            obj = json.loads(message)
            writer.write(pack(obj))
            await writer.drain()

    async def from_tcp_to_ws():
        try:
            while True:
                obj = await recv_frame(reader)
                await websocket.send(json.dumps(obj, separators=(",", ":")))
        except Exception:
            pass

    await asyncio.gather(from_ws_to_tcp(), from_tcp_to_ws())

async def main():
    print("WS Gateway on ws://127.0.0.1:8765 → TCP 127.0.0.1:9000")
    async with websockets.serve(proxy_connection, "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
