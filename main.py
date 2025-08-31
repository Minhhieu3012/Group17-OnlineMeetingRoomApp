#!/usr/bin/env python3
"""
HPH Meeting System - Main Launcher
Khởi động toàn bộ hệ thống video conferencing
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

# Import các server components
from server.tcp_server import main as tcp_main
from server.udp_server import UDPServer
from Client.gateway import Gateway
from advanced_feature import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("HPH-Main")

class HPHMeetingSystem:
    def __init__(self):
        self.tcp_task = None
        self.udp_task = None
        self.gateway_task = None
        self.running = False
        self.server_host = config.SERVER_HOST
        self.tcp_port = config.TCP_PORT
        self.udp_port = config.UDP_PORT
        self.gateway_port = config.GATEWAY_PORT

    async def start_tcp_server(self):
        """Khởi động TCP server cho chat, auth, file transfer"""
        logger.info("Starting TCP server...")
        try:
            await tcp_main(self.server_host, self.tcp_port)
        except Exception as e:
            logger.error(f"TCP server error: {e}")

    async def start_udp_server(self):
        """Khởi động UDP server cho voice/video"""
        logger.info("Starting UDP server...")
        try:
            udp_server = UDPServer(host=self.server_host, port=self.udp_port)
            await udp_server.start()
        except Exception as e:
            logger.error(f"UDP server error: {e}")

    async def start_gateway(self):
        """Khởi động WebSocket gateway"""
        logger.info("Starting WebSocket gateway...")
        try:
            gateway = Gateway(
                tcp_host=self.server_host,
                tcp_port=self.tcp_port,
                web_port=self.gateway_port
            )
            await gateway.start()
        except Exception as e:
            logger.error(f"Gateway error: {e}")

    async def start_all(self):
        """Khởi động tất cả các services"""
        logger.info("=" * 50)
        logger.info("HPH Meeting System Starting...")
        logger.info("=" * 50)
        logger.info(f"TCP Server: {self.server_host}:{self.tcp_port}")
        logger.info(f"UDP Server: {self.server_host}:{self.udp_port}")
        logger.info(f"Web Gateway: {self.server_host}:{self.gateway_port}")
        logger.info("=" * 50)

        self.running = True

        # Tạo tasks cho từng server
        self.tcp_task = asyncio.create_task(self.start_tcp_server())
        self.udp_task = asyncio.create_task(self.start_udp_server())
        self.gateway_task = asyncio.create_task(self.start_gateway())

        # Chờ tất cả tasks hoặc cho đến khi bị interrupt
        try:
            await asyncio.gather(
                self.tcp_task,
                self.udp_task,
                self.gateway_task,
                return_exceptions=True
            )
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Tắt tất cả services một cách graceful"""
        if not self.running:
            return

        logger.info("Shutting down HPH Meeting System...")
        self.running = False

        # Cancel tất cả tasks
        tasks = [self.tcp_task, self.udp_task, self.gateway_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()

        # Chờ tasks kết thúc
        await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
        logger.info("HPH Meeting System stopped")

    def update_config(self, args):
        """Update configuration with command line arguments"""
        self.server_host = args.host
        self.tcp_port = args.tcp_port
        self.udp_port = args.udp_port
        self.gateway_port = args.gateway_port

def setup_signal_handlers(system):
    """Setup signal handlers cho graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        # Tạo task để shutdown
        asyncio.create_task(system.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    parser = argparse.ArgumentParser(description="HPH Meeting System")
    parser.add_argument(
        "--component",
        choices=["all", "tcp", "udp", "gateway"],
        default="all",
        help="Which component to start (default: all)"
    )
    parser.add_argument(
        "--host",
        default=config.SERVER_HOST,
        help=f"Server host (default: {config.SERVER_HOST})"
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=config.TCP_PORT,
        help=f"TCP server port (default: {config.TCP_PORT})"
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=config.UDP_PORT,
        help=f"UDP server port (default: {config.UDP_PORT})"
    )
    parser.add_argument(
        "--gateway-port",
        type=int,
        default=config.GATEWAY_PORT,
        help=f"Gateway port (default: {config.GATEWAY_PORT})"
    )

    args = parser.parse_args()

    system = HPHMeetingSystem()
    system.update_config(args)
    setup_signal_handlers(system)

    try:
        if args.component == "all":
            await system.start_all()
        elif args.component == "tcp":
            await system.start_tcp_server()
        elif args.component == "udp":
            await system.start_udp_server()
        elif args.component == "gateway":
            await system.start_gateway()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"System error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("System interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
