import asyncio
import json
import webbrowser
import base64
from pathlib import Path
from aiohttp import web, WSMsgType
import aiohttp_cors
from server.protocol import send_any, read_any  

class Gateway:
    def __init__(self, tcp_host="127.0.0.1", tcp_port=8888, web_port=8080):
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.web_port = web_port
        self.static_dir = Path(__file__).parent / "static"

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        try:
            tcp_reader, tcp_writer = await asyncio.open_connection(
                self.tcp_host, self.tcp_port
            )
            print("[Gateway] Connected to TCP server")
        except Exception as e:
            print(f"[Gateway] Cannot connect to TCP server: {e}")
            await ws.close()
            return ws

        username = None
        aes_key = None  # ✅ sẽ lưu key sau khi login_ok

        async def _pump_ws_to_tcp():
            nonlocal username, aes_key
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)

                        # Nếu là login → gửi nguyên gốc (chưa có AES)
                        if data.get("type") == "login":
                            print(f"[DEBUG][Gateway] WS->TCP (login): {data}")
                            await self._send_tcp(tcp_writer, data, None)
                            continue

                        # Nếu đã login, chèn username thật
                        if username:
                            data["from"] = username

                        print(f"[DEBUG][Gateway] WS->TCP: {data}")
                        await self._send_tcp(tcp_writer, data, aes_key)
                    except Exception as e:
                        print(f"[Gateway] WS->TCP error: {e}")
                        break
                elif msg.type == WSMsgType.ERROR:
                    print(f"[Gateway] WebSocket error: {ws.exception()}")
                    break

        async def _pump_tcp_to_ws():
            nonlocal username, aes_key
            try:
                while True:
                    data = await read_any(tcp_reader, aes_key)
                    if data is None:
                        break

                    # Nếu login_ok → lưu username và aes_key
                    if data.get("type") == "login_ok":
                        username = data.get("username") or data.get("from")
                        aes_key_b64 = data.get("aes_key_b64")
                        if aes_key_b64:
                            aes_key = base64.b64decode(aes_key_b64)
                        print(f"[Gateway] User logged in as: {username}")

                    print(f"[DEBUG][Gateway] TCP->WS: {data}")
                    await ws.send_str(json.dumps(data))
            except Exception as e:
                print(f"[Gateway] TCP->WS error: {e}")

        ws_to_tcp_task = asyncio.create_task(_pump_ws_to_tcp())
        tcp_to_ws_task = asyncio.create_task(_pump_tcp_to_ws())

        try:
            await asyncio.wait(
                [ws_to_tcp_task, tcp_to_ws_task],
                return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            ws_to_tcp_task.cancel()
            tcp_to_ws_task.cancel()
            tcp_writer.close()
            await tcp_writer.wait_closed()

        return ws

    async def _send_tcp(self, tcp_writer, data, aes_key):
        """Gửi xuống TCP, có thể kèm AES"""
        await send_any(tcp_writer, data, aes_key)

    async def root_handler(self, request):
        return web.HTTPFound('/login.html')

    async def start(self):
        app = web.Application()

        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        app.router.add_get('/ws', self.websocket_handler)
        app.router.add_get('/', self.root_handler)

        if self.static_dir.exists():
            print(f"[Gateway] Serving static files from: {self.static_dir}")
            app.router.add_static('/', self.static_dir, name='static')
            static_files = list(self.static_dir.glob('*'))
            print(f"[Gateway] Available static files: {[f.name for f in static_files]}")
        else:
            print(f"[Gateway] Warning: Static directory not found: {self.static_dir}")
            self.static_dir.mkdir(exist_ok=True)
            print(f"[Gateway] Created static directory: {self.static_dir}")

        for route in list(app.router.routes()):
            cors.add(route)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.web_port)
        await site.start()

        print(f"[Gateway] WebSocket gateway running on http://localhost:{self.web_port}")
        print(f"[Gateway] TCP backend: {self.tcp_host}:{self.tcp_port}")

        try:
            webbrowser.open(f"http://localhost:{self.web_port}")
        except Exception as e:
            print(f"[Gateway] Could not open browser: {e}")

        await asyncio.Future()

if __name__ == "__main__":
    gateway = Gateway()
    asyncio.run(gateway.start())
