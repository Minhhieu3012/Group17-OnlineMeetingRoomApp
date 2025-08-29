#!/usr/bin/env python3
"""
HPH-meet Client Gateway (Python, aiohttp)
- Serves the Web UI on http://127.0.0.1:8080
- Web UI connects via ws://127.0.0.1:8080/ws-app to this gateway
- Gateway connects to the main server using TCP JSON lines (so "client connects to server by Python")
- Forwards JSON messages both ways (browser <-> gateway <-> server TCP)
"""
import os, asyncio, json, pathlib, logging
from aiohttp import web

# --- Config ---
SERVER_HOST = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))
HTTP_HOST   = os.environ.get("HTTP_HOST", "127.0.0.1")
HTTP_PORT   = int(os.environ.get("HTTP_PORT", "8080"))

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (contains 'web')
WEB_DIR = ROOT / "web"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

async def tcp_reader_to_ws(reader: asyncio.StreamReader, ws: web.WebSocketResponse):
    """Pump: server TCP -> browser WS"""
    try:
        while True:
            line = await reader.readline()
            if not line:
                logging.info("Upstream TCP closed.")
                await ws.close()
                break
            try:
                obj = json.loads(line.decode("utf-8").strip())
            except Exception as e:
                logging.warning(f"Parse from TCP failed: {e}")
                continue
            await ws.send_json(obj)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.warning(f"Reader pump error: {e}")

async def ws_to_tcp_writer(ws: web.WebSocketResponse, writer: asyncio.StreamWriter):
    """Pump: browser WS -> server TCP"""
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    obj = json.loads(msg.data)
                except Exception:
                    # ignore non-JSON text
                    continue
                data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
                writer.write(data)
                await writer.drain()
            elif msg.type == web.WSMsgType.ERROR:
                break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.warning(f"Writer pump error: {e}")

async def ws_app(request: web.Request):
    # Open TCP upstream per browser connection
    logging.info(f"WS connect from {request.remote}")
    try:
        reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
    except Exception as e:
        logging.error(f"Cannot connect upstream TCP {SERVER_HOST}:{SERVER_PORT}: {e}")
        return web.Response(text="Upstream unavailable", status=502)

    ws = web.WebSocketResponse(heartbeat=20.0)
    await ws.prepare(request)

    # start pumps
    task_r = asyncio.create_task(tcp_reader_to_ws(reader, ws))
    task_w = asyncio.create_task(ws_to_tcp_writer(ws, writer))

    # wait until tasks complete or error occurs
    try:
        await asyncio.gather(task_r, task_w)
    except Exception:
        pass
    finally:
        for t in (task_r, task_w):
            if not t.done():
                t.cancel()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        logging.info("WS disconnected.")
    
    return ws

async def index(request):
    return web.FileResponse(WEB_DIR / "index.html")

def create_app():
    app = web.Application()
    # WebSocket bridge endpoint
    app.router.add_get("/ws-app", ws_app)
    # Static files (serve / to web dir)
    app.router.add_get("/", index)
    app.router.add_static("/", path=str(WEB_DIR), name="static")
    return app

if __name__ == "__main__":
    app = create_app()
    logging.info(f"Serving Web UI from {WEB_DIR}")
    logging.info(f"Gateway on http://{HTTP_HOST}:{HTTP_PORT}  -> Upstream TCP {SERVER_HOST}:{SERVER_PORT}")
    web.run_app(app, host=HTTP_HOST, port=HTTP_PORT)