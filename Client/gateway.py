import asyncio
import json
import socket
import webbrowser
from pathlib import Path
from aiohttp import web, WSMsgType
import aiohttp_cors

class Gateway:
    def __init__(self, tcp_host="127.0.0.1", tcp_port=8888, web_port=8080):
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.web_port = web_port
        self.static_dir = Path(__file__).parent / "static"

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Kết nối tới TCP server
        try:
            tcp_reader, tcp_writer = await asyncio.open_connection(
                self.tcp_host, self.tcp_port
            )
            
            # Send gateway authentication message
            gateway_auth = {
                "type": "login",
                "payload": {
                    "username": "_gateway_",
                    "password": "gateway_internal_auth_2024"
                }
            }
            
            json_data = json.dumps(gateway_auth).encode()
            tcp_writer.write(len(json_data).to_bytes(4, 'big') + json_data)
            await tcp_writer.drain()
            
            # Wait for authentication response
            try:
                length_data = await asyncio.wait_for(tcp_reader.readexactly(4), timeout=5.0)
                length = int.from_bytes(length_data, 'big')
                response_data = await asyncio.wait_for(tcp_reader.readexactly(length), timeout=5.0)
                response = json.loads(response_data.decode())
                
                if not response.get("ok", False):
                    print(f"[Gateway] TCP authentication failed: {response.get('error', 'Unknown error')}")
                    await ws.close()
                    tcp_writer.close()
                    return ws
                    
                print("[Gateway] Successfully authenticated with TCP server")
                
            except asyncio.TimeoutError:
                print("[Gateway] TCP authentication timeout")
                await ws.close()
                tcp_writer.close()
                return ws
            except Exception as e:
                print(f"[Gateway] TCP authentication error: {e}")
                await ws.close()
                tcp_writer.close()
                return ws
                
        except Exception as e:
            print(f"[Gateway] Cannot connect to TCP server: {e}")
            await ws.close()
            return ws

        # Tạo tasks để pump data bidirectional
        ws_to_tcp_task = asyncio.create_task(
            self._pump_ws_to_tcp(ws, tcp_writer)
        )
        tcp_to_ws_task = asyncio.create_task(
            self._pump_tcp_to_ws(tcp_reader, ws)
        )

        # Chờ một trong hai tasks kết thúc
        try:
            await asyncio.wait(
                [ws_to_tcp_task, tcp_to_ws_task],
                return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            # Cleanup
            ws_to_tcp_task.cancel()
            tcp_to_ws_task.cancel()
            tcp_writer.close()
            await tcp_writer.wait_closed()

        return ws

    async def _pump_ws_to_tcp(self, ws, tcp_writer):
        """Pump messages from WebSocket to TCP"""
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    # Send to TCP server with length prefix
                    json_data = json.dumps(data).encode()
                    tcp_writer.write(len(json_data).to_bytes(4, 'big') + json_data)
                    await tcp_writer.drain()
                except Exception as e:
                    print(f"[Gateway] WS->TCP error: {e}")
                    break
            elif msg.type == WSMsgType.ERROR:
                print(f"[Gateway] WebSocket error: {ws.exception()}")
                break

    async def _pump_tcp_to_ws(self, tcp_reader, ws):
        """Pump messages from TCP to WebSocket"""
        try:
            while True:
                # Read length prefix
                length_data = await tcp_reader.readexactly(4)
                length = int.from_bytes(length_data, 'big')
                
                # Read JSON data
                json_data = await tcp_reader.readexactly(length)
                data = json.loads(json_data.decode())
                
                await ws.send_str(json.dumps(data))
        except Exception as e:
            print(f"[Gateway] TCP->WS error: {e}")

    async def root_handler(self, request):
        """Redirect root to login page"""
        return web.HTTPFound('/login.html')

    async def start(self):
        app = web.Application()
        
        # CORS setup
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        # Routes
        app.router.add_get('/ws', self.websocket_handler)
        
        app.router.add_get('/', self.root_handler)
        
        # Static files
        if self.static_dir.exists():
            print(f"[Gateway] Serving static files from: {self.static_dir}")
            app.router.add_static('/', self.static_dir, name='static')
            
            # List static files for debugging
            static_files = list(self.static_dir.glob('*'))
            print(f"[Gateway] Available static files: {[f.name for f in static_files]}")
        else:
            print(f"[Gateway] Warning: Static directory not found: {self.static_dir}")
            # Create static directory if it doesn't exist
            self.static_dir.mkdir(exist_ok=True)
            print(f"[Gateway] Created static directory: {self.static_dir}")
        
        # Add CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)

        try:
            # Start server
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', self.web_port)
            await site.start()

            print(f"[Gateway] WebSocket gateway running on http://localhost:{self.web_port}")
            print(f"[Gateway] TCP backend: {self.tcp_host}:{self.tcp_port}")
            
            # Auto-open browser
            try:
                webbrowser.open(f"http://localhost:{self.web_port}")
            except Exception as e:
                print(f"[Gateway] Could not open browser: {e}")

            # Keep running
            await asyncio.Future()
        except OSError as e:
            if e.errno == 10048:  # Windows port already in use
                print(f"[Gateway] Error: Port {self.web_port} is already in use!")
                print(f"[Gateway] Please close other instances or use a different port")
                raise
            else:
                raise

if __name__ == "__main__":
    gateway = Gateway()
    asyncio.run(gateway.start())
