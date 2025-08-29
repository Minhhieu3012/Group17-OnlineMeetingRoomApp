
import os
import asyncio
import json
import logging
import webbrowser
from pathlib import Path
from aiohttp import web

# -------------------- Config qua ENV --------------------
SERVER_HOST = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))
HTTP_HOST   = os.environ.get("HTTP_HOST", "127.0.0.1")
HTTP_PORT   = int(os.environ.get("HTTP_PORT", "8080"))
AUTO_OPEN   = os.environ.get("AUTO_OPEN", "1").lower() not in ("0", "false", "no")

# Thư mục tĩnh: ưu tiên Client/static (file này ở Client/gateway.py)
ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR  = ROOT_DIR / "static"
# Fallback nhẹ nếu đổi tên thư mục web
if not WEB_DIR.exists():
    for cand in (ROOT_DIR / "Web", ROOT_DIR / "web", ROOT_DIR.parent / "web", ROOT_DIR.parent / "Web"):
        if cand.exists():
            WEB_DIR = cand
            break

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# -------------------- Bridge Pumps --------------------
async def tcp_reader_to_ws(reader: asyncio.StreamReader, ws: web.WebSocketResponse) -> None:
    """
    Nhận dữ liệu từ TCP server (JSON mỗi dòng) và gửi sang browser WS dưới dạng JSON.
    """
    try:
        while True:
            line = await reader.readline()
            if not line:
                logging.info("Upstream TCP closed connection.")
                await ws.close()
                break

            text = line.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            try:
                obj = json.loads(text)
                await ws.send_json(obj)
            except Exception:
                # Nếu server gửi không phải JSON hợp lệ, chuyển thành text để debug
                await ws.send_str(text)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.warning(f"Reader pump error: {e}")


async def ws_to_tcp_writer(ws: web.WebSocketResponse, writer: asyncio.StreamWriter) -> None:
    """
    Nhận dữ liệu TEXT từ browser WS (dự kiến là JSON) và đẩy vào TCP (thêm '\n').
    """
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = msg.data.strip()
                # Ưu tiên giữ nguyên JSON hợp lệ; nếu không hợp lệ, bọc lại để TCP server vẫn đọc được
                try:
                    _ = json.loads(data)
                    payload = (data + "\n").encode("utf-8")
                except Exception:
                    payload = (json.dumps({"type": "raw", "data": data}, ensure_ascii=False) + "\n").encode("utf-8")

                writer.write(payload)
                await writer.drain()

            elif msg.type == web.WSMsgType.BINARY:
                # Không xử lý binary trong scope hiện tại
                continue

            elif msg.type == web.WSMsgType.ERROR:
                break

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.warning(f"Writer pump error: {e}")

# -------------------- HTTP/WS Handlers --------------------
async def ws_app(request: web.Request) -> web.StreamResponse:
    """
    Mỗi kết nối WS từ trình duyệt sẽ mở một kết nối TCP tới server.
    """
    logging.info(f"WS connect from {request.remote}")
    try:
        reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
    except Exception as e:
        logging.error(f"Cannot connect to TCP {SERVER_HOST}:{SERVER_PORT}: {e}")
        return web.Response(text="Upstream TCP unavailable", status=502)

    ws = web.WebSocketResponse(heartbeat=20.0)
    await ws.prepare(request)

    # Chạy 2 luồng bơm dữ liệu song song
    task_r = asyncio.create_task(tcp_reader_to_ws(reader, ws))
    task_w = asyncio.create_task(ws_to_tcp_writer(ws, writer))

    # Chờ đến khi WS đóng
    await ws.wait_closed()
    for t in (task_r, task_w):
        t.cancel()

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

    logging.info("WS disconnected.")
    return ws


async def index(_request: web.Request) -> web.FileResponse:
    """
    Truy cập '/' sẽ trả về trang login.html (đa trang).
    """
    return web.FileResponse(WEB_DIR / "login.html")


async def open_browser(_app: web.Application) -> None:
    """
    Tự mở trình duyệt tới trang đăng nhập khi server khởi động.
    Có thể tắt qua AUTO_OPEN=0.
    """
    if not AUTO_OPEN:
        return
    await asyncio.sleep(0.35)  # đợi server bind cổng xong
    url = f"http://{HTTP_HOST}:{HTTP_PORT}/login.html"
    try:
        webbrowser.open(url)
        logging.info(f"Opened browser at {url}")
    except Exception as e:
        logging.warning(f"Không mở được trình duyệt tự động: {e}")


def create_app() -> web.Application:
    if not WEB_DIR.exists():
        raise RuntimeError(f"Static directory not found: {WEB_DIR}")

    app = web.Application()
    # WebSocket bridge
    app.router.add_get("/ws-app", ws_app)
    # Route gốc -> login.html
    app.router.add_get("/", index)
    # Phục vụ tĩnh tất cả file trong thư mục web (login.html, lobby.html, room.html, common.js, styles.css, ...)
    app.router.add_static("/", path=str(WEB_DIR), name="static")

    # Auto-open browser sau khi server start (nếu bật)
    app.on_startup.append(open_browser)
    return app


if __name__ == "__main__":
    logging.info(f"Serving static from: {WEB_DIR}")
    logging.info(f"Gateway: http://{HTTP_HOST}:{HTTP_PORT}  ->  TCP upstream {SERVER_HOST}:{SERVER_PORT}")
    web.run_app(create_app(), host=HTTP_HOST, port=HTTP_PORT)
