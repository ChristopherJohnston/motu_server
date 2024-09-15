import asyncio
import logging
from os import wait
import socket
from typing import List, Optional
import uuid
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

logger = logging.getLogger(__name__)

class AsyncRunner:
    def __init__(self, ip_version: IPVersion) -> None:
        self.ip_version = ip_version
        self.aiozc: Optional[AsyncZeroconf] = None

    async def register_services(self, infos: List[AsyncServiceInfo]) -> None:
        self.aiozc = AsyncZeroconf(ip_version=self.ip_version)
        tasks = [self.aiozc.async_register_service(info) for info in infos]
        background_tasks = await asyncio.gather(*tasks)
        await asyncio.gather(*background_tasks)
        logger.info("Registration Complete")

    async def unregister_services(self, infos: List[AsyncServiceInfo]) -> None:
        assert self.aiozc is not None
        tasks = [self.aiozc.async_unregister_service(info) for info in infos]
        background_tasks = await asyncio.gather(*tasks)
        await asyncio.gather(*background_tasks)
        await self.aiozc.async_close()
        logger.info("Unregistration complete")

class MotuZeroConfRegistration:
    async def register(self, server_name="Motu Test Server"):
        logger.info(f"Registering Server for MOTU Discovery using zeroconf as '{server_name}'")
        ip_version = IPVersion.All
        hostname = socket.gethostname()
        server_uid = uuid.uuid4().hex[:16]

        self.infos = [
            AsyncServiceInfo(
                "_http._tcp.local.",
                f"{server_name}._http._tcp.local.",
                addresses=[socket.inet_aton("127.0.0.1")],
                port=80,
                properties={
                    b'motu.mdns.type': b'netiodevice',
                    b'uid': server_uid,
                    b'apiversion': b'0.0.0'
                },
                server=f"{hostname}.",
            ),
            #  AsyncServiceInfo(
            #      '_motu-csr._udp.local.',
            #      f'{server_name}._motu-csr._udp.local.',
            #      addresses=[socket.inet_aton("127.0.0.1")],
            #      port=9999,
            #      weight=0,
            #      priority=0,
            #      server=f'{hostname}.',
            #      properties={b'': None},
            #      interface_index=None
            # ),
            # AsyncServiceInfo(
            #     '_osc._udp.local.',
            #     f'{server_name}._osc._udp.local.',
            #     addresses=[b'\xc0\xa8\x01\xb3'],
            #     port=9998,
            #     properties={},
            #     server=f'{hostname}.',
            # )
        ]
        self.runner = AsyncRunner(ip_version)
        await self.runner.register_services(self.infos)
        
    async def unregister(self):
        logger.info("Unregistering MOTU server using zeroconf...")
        await self.runner.unregister_services(self.infos)
        