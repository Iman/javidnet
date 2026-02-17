"""
JavidNet — Local Proxy

The user-facing entry point.  Run this on your phone/laptop,
configure your apps to use SOCKS5 at 127.0.0.1:1080, and your
traffic exits through JavidNet's satellite gateways.

Supports:
  • SOCKS5 (TCP CONNECT) — works with browsers, curl, most apps
  • DNS tunneling — queries go through mesh, never touch domestic DNS
  • Smart routing — picks the best gateway automatically

Setup:
  Firefox:  Settings → Network → Manual Proxy → SOCKS5 127.0.0.1:1080
  Telegram: Settings → Data → Proxy → SOCKS5 127.0.0.1:1080
  curl:     curl --proxy socks5h://127.0.0.1:1080 https://example.com
"""
import struct
import asyncio
import logging
from typing import Callable, Optional, Tuple

logger = logging.getLogger("javidnet.proxy")

# SOCKS5 protocol constants
SOCKS_VER = 0x05
AUTH_NONE = 0x00
CMD_CONNECT = 0x01
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03
ATYP_IPV6 = 0x04
REP_OK = 0x00
REP_FAIL = 0x01
REP_UNREACHABLE = 0x04


class LocalProxy:
    """
    SOCKS5 proxy that routes traffic through the JavidNet mesh.

        async def connect(host, port):
            return (reader, writer)  # via mesh → gateway

        proxy = LocalProxy(port=1080, connect_fn=connect)
        await proxy.serve()
    """

    def __init__(self, port: int = 1080, connect_fn: Callable = None,
                 bind: str = "127.0.0.1"):
        self.port = port
        self.bind = bind
        self._connect_fn = connect_fn
        self._active = 0
        self._total = 0
        self._bytes_in = 0
        self._bytes_out = 0

    async def serve(self):
        server = await asyncio.start_server(
            self._handle, self.bind, self.port,
        )
        logger.info(f"SOCKS5 proxy on {self.bind}:{self.port}")
        async with server:
            await server.serve_forever()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._active += 1
        self._total += 1
        try:
            # SOCKS5 handshake
            ver = await reader.readexactly(1)
            if ver[0] != SOCKS_VER:
                return
            nmethods = (await reader.readexactly(1))[0]
            await reader.readexactly(nmethods)

            writer.write(bytes([SOCKS_VER, AUTH_NONE]))
            await writer.drain()

            # CONNECT request
            header = await reader.readexactly(4)
            _, cmd, _, atyp = header
            if cmd != CMD_CONNECT:
                self._reply(writer, REP_FAIL)
                return

            # Parse destination
            if atyp == ATYP_IPV4:
                raw = await reader.readexactly(4)
                host = ".".join(str(b) for b in raw)
            elif atyp == ATYP_DOMAIN:
                dlen = (await reader.readexactly(1))[0]
                host = (await reader.readexactly(dlen)).decode()
            elif atyp == ATYP_IPV6:
                raw = await reader.readexactly(16)
                host = ":".join(f"{raw[i]:02x}{raw[i+1]:02x}" for i in range(0, 16, 2))
            else:
                self._reply(writer, REP_FAIL)
                return

            port = struct.unpack(">H", await reader.readexactly(2))[0]
            logger.debug(f"CONNECT {host}:{port}")

            # Route through mesh → gateway → satellite → internet
            try:
                remote_r, remote_w = await asyncio.wait_for(
                    self._connect_fn(host, port), timeout=20,
                )
            except Exception as e:
                logger.debug(f"Connection failed: {host}:{port} — {e}")
                self._reply(writer, REP_UNREACHABLE)
                return

            # Success
            self._reply(writer, REP_OK)

            # Bidirectional relay
            await asyncio.gather(
                self._pipe(reader, remote_w, "→"),
                self._pipe(remote_r, writer, "←"),
            )

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as e:
            logger.debug(f"Proxy error: {e}")
        finally:
            self._active -= 1
            writer.close()

    def _reply(self, writer, status):
        writer.write(bytes([SOCKS_VER, status, 0x00, ATYP_IPV4, 0, 0, 0, 0, 0, 0]))

    async def _pipe(self, reader, writer, direction):
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
                if direction == "→":
                    self._bytes_out += len(data)
                else:
                    self._bytes_in += len(data)
        except Exception:
            pass

    def stats(self):
        return {
            "active_connections": self._active,
            "total_connections": self._total,
            "bytes_in": self._bytes_in,
            "bytes_out": self._bytes_out,
        }
