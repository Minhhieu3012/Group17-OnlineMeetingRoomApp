#!/usr/bin/env python3

import asyncio
import argparse
import logging
import signal
import sys

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
    def __init__(self, host: str, tcp_port: int, udp_port: int, gateway_port: int):
        self.tcp_task: asyncio.Task | None = None
        self.udp_task: asyncio.Task | None = None
        self.gateway_task: asyncio.Task | None = None
        self.running = False
        self.server_host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.gateway_port = gateway_port

    async def start_tcp_server(self):
        logger.info("Starting TCP server...")
        try:
            await tcp_main(self.server_host, self.tcp_port)
        except asyncio.CancelledError:
            logger.info("TCP server task cancelled")
            raise
        except Exception as e:
            logger.exception(f"TCP server error: {e}")

    async def start_udp_server(self):
        logger.info("Starting UDP server...")
        try:
            udp_server = UDPServer(host=self.server_host, port=self.udp_port)
            await udp_server.start()
        except asyncio.CancelledError:
            logger.info("UDP server task cancelled")
            raise
        except Exception as e:
            logger.exception(f"UDP server error: {e}")

    async def start_gateway(self):
        logger.info("Starting WebSocket gateway...")
        try:
            gateway = Gateway(
                tcp_host=self.server_host,
                tcp_port=self.tcp_port,
                web_port=self.gateway_port,
            )
            await gateway.start()
        except asyncio.CancelledError:
            logger.info("Gateway task cancelled")
            raise
        except Exception as e:
            logger.exception(f"Gateway error: {e}")

    async def _run_tasks(self, tasks: list[asyncio.Task]):
        self.running = True
        try:
            await asyncio.gather(*tasks, return_exceptions=False)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def start_all(self):
        logger.info("=" * 56)
        logger.info("HPH Meeting System Starting (ALL)...")
        logger.info("=" * 56)
        logger.info(f"TCP Server:    {self.server_host}:{self.tcp_port}")
        logger.info(f"UDP Server:    {self.server_host}:{self.udp_port}")
        logger.info(f"Web Gateway:   {self.server_host}:{self.gateway_port}")
        logger.info("=" * 56)
        self.tcp_task = asyncio.create_task(self.start_tcp_server())
        self.udp_task = asyncio.create_task(self.start_udp_server())
        self.gateway_task = asyncio.create_task(self.start_gateway())
        await self._run_tasks([self.tcp_task, self.udp_task, self.gateway_task])

    async def start_servers(self):
        logger.info("=" * 56)
        logger.info("HPH Meeting System Starting (SERVERS: TCP+UDP)...")
        logger.info("=" * 56)
        logger.info(f"TCP Server:    {self.server_host}:{self.tcp_port}")
        logger.info(f"UDP Server:    {self.server_host}:{self.udp_port}")
        logger.info("=" * 56)
        self.tcp_task = asyncio.create_task(self.start_tcp_server())
        self.udp_task = asyncio.create_task(self.start_udp_server())
        await self._run_tasks([self.tcp_task, self.udp_task])

    async def shutdown(self):
        if not self.running:
            return
        logger.info("Shutting down HPH Meeting System...")
        self.running = False
        tasks = [t for t in [self.tcp_task, self.udp_task, self.gateway_task] if t]
        for t in tasks:
            if not t.done():
                t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("HPH Meeting System stopped")


def setup_signal_handlers(system: HPHMeetingSystem):
    loop = asyncio.get_running_loop()

    def _handler():
        logger.info("Received termination signal")
        asyncio.create_task(system.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handler)
        except NotImplementedError:
            # Windows may not support signal handlers in ProactorEventLoop
            signal.signal(sig, lambda *_: asyncio.create_task(system.shutdown()))


async def main():
    parser = argparse.ArgumentParser(description="HPH Meeting System")
    parser.add_argument(
        "--component",
        choices=["all", "servers", "tcp", "udp", "gateway"],
        default="all",
        help="Which component to start (default: all)"
    )
    parser.add_argument("--host", default=config.SERVER_HOST)
    parser.add_argument("--tcp-port", type=int, default=config.TCP_PORT)
    parser.add_argument("--udp-port", type=int, default=config.UDP_PORT)
    parser.add_argument("--gateway-port", type=int, default=config.GATEWAY_PORT)

    args = parser.parse_args()

    system = HPHMeetingSystem(args.host, args.tcp_port, args.udp_port, args.gateway_port)
    setup_signal_handlers(system)

    try:
        if args.component == "all":
            await system.start_all()
        elif args.component == "servers":
            await system.start_servers()
        elif args.component == "tcp":
            await system.start_tcp_server()
        elif args.component == "udp":
            await system.start_udp_server()
        elif args.component == "gateway":
            await system.start_gateway()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"System error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("System interrupted")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
