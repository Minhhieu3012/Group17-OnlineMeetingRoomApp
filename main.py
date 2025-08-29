#!/usr/bin/env python3
"""
HPH-meet Main Server Entry Point
Starts all required servers (TCP, UDP, Gateway) in parallel
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# đảm bảo Python tìm thấy module trong folder server và Client
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "server"))
sys.path.append(str(BASE_DIR / "Client"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s: %(message)s"
)
logger = logging.getLogger("HPH-Main")

async def start_tcp_server():
    """Start the TCP server for chat and signaling"""
    from tcp_server import main as tcp_main
    logger.info("Starting TCP server on port 8000...")
    await tcp_main()

async def start_udp_server():
    """Start the UDP server for media streaming"""
    from udp_server import UDPServer
    logger.info("Starting UDP server on port 6000...")
    server = UDPServer(host="0.0.0.0", port=6000)
    await server.start()

async def start_gateway():
    """Start the HTTP/WebSocket gateway"""
    from gateway import create_app
    from aiohttp import web
    
    logger.info("Starting HTTP/WebSocket gateway on port 5000...")
    app = create_app()
    
    os.environ.setdefault("SERVER_HOST", "127.0.0.1")
    os.environ.setdefault("SERVER_PORT", "8000")
    os.environ.setdefault("HTTP_HOST", "0.0.0.0")
    os.environ.setdefault("HTTP_PORT", "5000")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=5000)
    await site.start()
    
    try:
        await asyncio.Future()  # run forever
    except asyncio.CancelledError:
        await runner.cleanup()

async def main():
    logger.info("HPH-meet Server Starting...")
    logger.info("Frontend will be available at: http://localhost:5000")
    logger.info("TCP Server (Chat/Signaling): port 8000")
    logger.info("UDP Server (Media): port 6000")
    
    tasks = [
        asyncio.create_task(start_tcp_server()),
        asyncio.create_task(start_udp_server()),
        asyncio.create_task(start_gateway())
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
