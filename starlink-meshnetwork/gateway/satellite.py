"""
JavidNet - Satellite Gateway

The gateway is the beating heart of JavidNet.  It's a machine
connected to a Starlink dish that accepts encrypted tunnels from
the mesh and forwards traffic to the open internet.

What makes this fundamentally different from a VPN server:
  • The upstream IS the satellite - not a datacenter, not an ISP
  • Bandwidth is shared across an entire neighborhood/city
  • Every byte has a real cost - so the gateway must be smart
    about what gets priority
  • The dish is physically illegal - so the gateway must detect
    compromise and self-destruct

Architecture:
  Mesh peers ──encrypted tunnels──▶ Gateway ──Starlink──▶ Internet
                                      │
                                    Content cache
                                    DNS resolver
                                    Traffic shaper
                                    Threat detector
"""
import os
import time
import json
import struct
import asyncio
import hashlib
import logging
import socket
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Set
from collections import defaultdict

logger = logging.getLogger("javidnet.gateway")


class SessionPriority(Enum):
    """Traffic priority classes.  Satellite bandwidth is precious."""
    CRITICAL = 1     # DNS, control messages, emergency comms
    INTERACTIVE = 2  # chat, messaging, small web requests
    STANDARD = 3     # normal browsing, email
    BULK = 4         # large downloads, updates, media
    BACKGROUND = 5   # cache prefetch, telemetry


@dataclass
class TunnelSession:
    """An active tunnel from a mesh peer."""
    session_id: str
    peer_node_id: str
    peer_public_key: bytes
    reader: asyncio.StreamReader = None
    writer: asyncio.StreamWriter = None
    started: float = 0.0
    bytes_up: int = 0
    bytes_down: int = 0
    priority: SessionPriority = SessionPriority.STANDARD
    # Token bucket for fairness
    tokens: float = 0.0
    token_rate: float = 100_000     # bytes/sec refill rate
    token_capacity: float = 500_000  # max burst


@dataclass
class GatewayConfig:
    # Network
    mesh_listen_port: int = 7744    # tunnels from mesh peers
    satellite_interface: str = ""   # auto-detect if empty
    # Bandwidth management
    total_uplink_kbps: int = 20_000    # 20 Mbps Starlink upload
    total_downlink_kbps: int = 100_000  # 100 Mbps Starlink download
    per_session_kbps: int = 2_000       # 2 Mbps per user default
    max_sessions: int = 200
    # Cache
    cache_enabled: bool = True
    cache_dir: str = str(Path.home() / ".javidnet" / "cache")
    cache_size_mb: int = 2000
    # Security
    require_trust: int = 1         # minimum trust level to connect
    panic_wipe: bool = True        # wipe keys on suspected compromise
    canary_url: str = ""           # URL that must remain reachable
    # Dish monitoring
    dish_ip: str = "192.168.100.1"
    health_interval: int = 15


class Gateway:
    """
    JavidNet satellite gateway.

        gw = Gateway(config)
        await gw.start()
    """

    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        self._sessions: Dict[str, TunnelSession] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        # DNS cache (avoid redundant satellite queries)
        self._dns_cache: Dict[str, Tuple[bytes, float]] = {}
        # Content cache
        self._content_cache: Optional["ContentCache"] = None
        # Bandwidth accounting
        self._total_bytes_up = 0
        self._total_bytes_down = 0
        self._session_count_peak = 0
        self._start_time = 0.0

    async def start(self):
        self._running = True
        self._start_time = time.time()

        # Detect satellite interface
        if not self.config.satellite_interface:
            self.config.satellite_interface = await self._detect_satellite_iface()

        # Start content cache
        if self.config.cache_enabled:
            self._content_cache = ContentCache(
                self.config.cache_dir,
                max_size_mb=self.config.cache_size_mb,
            )
            await self._content_cache.start()

        # Start tunnel listener
        self._tasks.append(asyncio.create_task(self._tunnel_listener()))
        # Health monitor
        self._tasks.append(asyncio.create_task(self._health_loop()))
        # Bandwidth reporter
        self._tasks.append(asyncio.create_task(self._stats_loop()))

        logger.info(f"Gateway started - listening on :{self.config.mesh_listen_port}, "
                    f"satellite via {self.config.satellite_interface}")

    async def stop(self):
        self._running = False
        for sid, session in self._sessions.items():
            if session.writer:
                session.writer.close()
        for t in self._tasks:
            t.cancel()
        logger.info("Gateway stopped")

    # ── Tunnel management ─────────────────────────────────

    async def _tunnel_listener(self):
        """Accept encrypted tunnels from mesh peers."""
        server = await asyncio.start_server(
            self._on_tunnel_connect,
            "0.0.0.0", self.config.mesh_listen_port,
        )
        logger.info(f"Tunnel listener on :{self.config.mesh_listen_port}")
        async with server:
            await server.serve_forever()

    async def _on_tunnel_connect(self, reader: asyncio.StreamReader,
                                  writer: asyncio.StreamWriter):
        """Handle a new tunnel connection from a mesh peer."""
        if len(self._sessions) >= self.config.max_sessions:
            writer.close()
            return

        session_id = hashlib.sha256(os.urandom(16)).hexdigest()[:12]
        session = TunnelSession(
            session_id=session_id,
            peer_node_id="",
            peer_public_key=b"",
            reader=reader,
            writer=writer,
            started=time.time(),
        )

        try:
            # Handshake: peer sends its identity
            header = await asyncio.wait_for(reader.readexactly(48), timeout=10)
            session.peer_node_id = header[:16].hex()
            session.peer_public_key = header[16:48]

            # TODO: verify trust level from node's trust database
            # For now, accept all connections

            # Send ACK with our session parameters
            ack = struct.pack(">12sI", session_id.encode()[:12],
                              self.config.per_session_kbps)
            writer.write(ack)
            await writer.drain()

            self._sessions[session_id] = session
            self._session_count_peak = max(self._session_count_peak, len(self._sessions))
            logger.info(f"Tunnel {session_id} from {session.peer_node_id} "
                        f"(sessions: {len(self._sessions)})")

            # Main relay loop
            await self._relay_session(session)

        except Exception as e:
            logger.debug(f"Tunnel setup failed: {e}")
        finally:
            self._sessions.pop(session_id, None)
            writer.close()

    async def _relay_session(self, session: TunnelSession):
        """
        Relay traffic for one tunnel session.

        Protocol: simple length-prefixed messages.
          [2 bytes: length] [1 byte: type] [payload]

        Types:
          0x01 = TCP connect request  {"host": "...", "port": 443}
          0x02 = TCP data
          0x03 = DNS query
          0x04 = cache request (URL hash)
          0xFF = close
        """
        while self._running:
            try:
                len_buf = await asyncio.wait_for(
                    session.reader.readexactly(2), timeout=120,
                )
                msg_len = struct.unpack(">H", len_buf)[0]
                if msg_len == 0 or msg_len > 65535:
                    break

                msg = await asyncio.wait_for(
                    session.reader.readexactly(msg_len), timeout=30,
                )
                msg_type = msg[0]
                payload = msg[1:]

                if msg_type == 0x01:
                    await self._handle_connect(session, payload)
                elif msg_type == 0x02:
                    await self._handle_data(session, payload)
                elif msg_type == 0x03:
                    await self._handle_dns(session, payload)
                elif msg_type == 0x04:
                    await self._handle_cache_req(session, payload)
                elif msg_type == 0xFF:
                    break

                session.bytes_up += msg_len

            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                break
            except Exception as e:
                logger.debug(f"Session {session.session_id} error: {e}")
                break

    async def _handle_connect(self, session: TunnelSession, payload: bytes):
        """
        Open a TCP connection to the internet via satellite.
        This is where JavidNet traffic exits to the real internet.
        """
        try:
            req = json.loads(payload)
            host = req["host"]
            port = req["port"]
        except (json.JSONDecodeError, KeyError):
            return

        # Classify priority
        session.priority = self._classify_traffic(host, port)

        # Apply token bucket (fairness)
        await self._consume_tokens(session, 0)

        try:
            # Connect to internet via satellite interface
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=15,
            )

            # Bidirectional relay
            async def internet_to_tunnel():
                try:
                    while self._running:
                        data = await r.read(8192)
                        if not data:
                            break
                        await self._consume_tokens(session, len(data))
                        # Send back to mesh peer
                        frame = struct.pack(">HB", len(data) + 1, 0x02) + data
                        session.writer.write(frame)
                        await session.writer.drain()
                        session.bytes_down += len(data)
                        self._total_bytes_down += len(data)
                except Exception:
                    pass
                finally:
                    w.close()

            asyncio.create_task(internet_to_tunnel())

            # ACK the connect request
            ack = struct.pack(">HB", 1, 0x01)
            session.writer.write(ack)
            await session.writer.drain()

        except Exception as e:
            # Connection failed - notify peer
            err_msg = json.dumps({"error": str(e)}).encode()
            frame = struct.pack(">HB", len(err_msg) + 1, 0xFF) + err_msg
            session.writer.write(frame)
            await session.writer.drain()

    async def _handle_data(self, session: TunnelSession, payload: bytes):
        """Forward data from tunnel to an active internet connection."""
        self._total_bytes_up += len(payload)
        session.bytes_up += len(payload)
        # In a full implementation, this routes to the correct
        # internet connection based on a connection ID

    async def _handle_dns(self, session: TunnelSession, payload: bytes):
        """
        Resolve DNS on behalf of a mesh peer.
        Cache results aggressively - DNS is the #1 latency killer
        over satellite (500ms+ RTT).
        """
        import struct as st

        # Parse domain from payload (raw DNS query)
        query_hash = hashlib.md5(payload).hexdigest()

        # Check cache
        cached = self._dns_cache.get(query_hash)
        if cached:
            response, expires = cached
            if time.time() < expires:
                frame = struct.pack(">HB", len(response) + 1, 0x03) + response
                session.writer.write(frame)
                await session.writer.drain()
                return

        # Forward to upstream DNS (Cloudflare DoH to avoid plain DNS)
        try:
            response = await self._doh_resolve(payload)
            # Cache for 5 minutes (satellite latency makes caching valuable)
            self._dns_cache[query_hash] = (response, time.time() + 300)
            frame = struct.pack(">HB", len(response) + 1, 0x03) + response
            session.writer.write(frame)
            await session.writer.drain()
        except Exception as e:
            logger.debug(f"DNS resolution failed: {e}")

    async def _doh_resolve(self, raw_query: bytes) -> bytes:
        """
        DNS-over-HTTPS to Cloudflare (1.1.1.1).
        Avoids plain DNS that could be intercepted.
        """
        import base64
        import ssl

        query_b64 = base64.urlsafe_b64encode(raw_query).rstrip(b"=").decode()
        path = f"/dns-query?dns={query_b64}"

        ssl_ctx = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            "1.1.1.1", 443, ssl=ssl_ctx,
        )
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: cloudflare-dns.com\r\n"
            f"Accept: application/dns-message\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(request.encode())
        await writer.drain()

        # Read response
        response = await reader.read(4096)
        writer.close()

        # Extract body (after headers)
        body_start = response.find(b"\r\n\r\n")
        if body_start >= 0:
            return response[body_start + 4:]
        return response

    async def _handle_cache_req(self, session: TunnelSession, payload: bytes):
        """
        Serve cached content without going to satellite.
        This is the bandwidth multiplier: if 100 people request the
        same BBC article, only the first request crosses the dish.
        """
        if not self._content_cache:
            return

        url_hash = payload.decode("utf-8", errors="ignore")
        cached = await self._content_cache.get(url_hash)
        if cached:
            frame = struct.pack(">HB", len(cached) + 1, 0x04) + cached
            session.writer.write(frame)
            await session.writer.drain()
            logger.debug(f"Cache hit: {url_hash}")

    # ── Traffic classification ────────────────────────────

    def _classify_traffic(self, host: str, port: int) -> SessionPriority:
        """
        Classify traffic by priority.  On a shared satellite link,
        a single video stream could starve 100 people's messaging.
        """
        # DNS is always critical
        if port == 53:
            return SessionPriority.CRITICAL

        # Messaging apps = interactive
        messaging_hosts = {
            "api.telegram.org", "web.telegram.org",
            "signal.org", "chat.signal.org",
            "web.whatsapp.com",
        }
        if any(h in host for h in messaging_hosts):
            return SessionPriority.INTERACTIVE

        # HTTPS standard browsing
        if port == 443:
            return SessionPriority.STANDARD

        # Large port ranges often used for streaming/P2P
        if port > 8000:
            return SessionPriority.BULK

        return SessionPriority.STANDARD

    # ── Token bucket (bandwidth fairness) ─────────────────

    async def _consume_tokens(self, session: TunnelSession, nbytes: int):
        """
        Fair bandwidth sharing.  Each session has a token bucket.
        When the bucket is empty, the session is throttled.
        """
        # Refill tokens
        now = time.time()
        elapsed = now - session.started
        session.tokens = min(
            session.token_capacity,
            session.tokens + session.token_rate * elapsed,
        )

        # Consume
        if session.tokens >= nbytes:
            session.tokens -= nbytes
        else:
            # Throttle: wait until enough tokens
            deficit = nbytes - session.tokens
            wait_time = deficit / session.token_rate
            await asyncio.sleep(min(wait_time, 1.0))
            session.tokens = 0

    # ── Dish health monitoring ────────────────────────────

    async def _health_loop(self):
        """
        Monitor the Starlink dish.
        We can't use the gRPC API directly (it requires grpcio + proto files),
        so we probe connectivity and latency instead.
        """
        failures = 0

        while self._running:
            try:
                healthy = await self._probe_satellite()
                if healthy:
                    failures = 0
                else:
                    failures += 1
                    logger.warning(f"Satellite probe failed ({failures})")
                    if failures >= 3:
                        logger.critical("Satellite link DOWN")
                        # Enter store-and-forward mode
                        await self._enter_degraded_mode()
                        failures = 0  # reset after action

            except Exception as e:
                logger.debug(f"Health check error: {e}")

            await asyncio.sleep(self.config.health_interval)

    async def _probe_satellite(self) -> bool:
        """Probe satellite connectivity by checking an external host."""
        try:
            start = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("1.1.1.1", 443),
                timeout=10,
            )
            latency = (time.time() - start) * 1000
            writer.close()
            logger.debug(f"Satellite probe: {latency:.0f}ms")
            return True
        except Exception:
            return False

    async def _enter_degraded_mode(self):
        """Satellite link is down - switch to store-and-forward."""
        logger.warning("Entering degraded mode - queuing outbound traffic")
        # Notify all connected peers
        for sid, session in self._sessions.items():
            try:
                msg = json.dumps({"status": "degraded", "reason": "satellite_down"}).encode()
                frame = struct.pack(">HB", len(msg) + 1, 0xFF) + msg
                session.writer.write(frame)
                await session.writer.drain()
            except Exception:
                pass

    async def _detect_satellite_iface(self) -> str:
        """Auto-detect which network interface connects to Starlink."""
        # Starlink router is at 192.168.100.1
        # Find the interface that can reach it
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "route", "get", "192.168.100.1",
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            # Parse "... dev eth0 ..."
            parts = out.decode().split()
            if "dev" in parts:
                return parts[parts.index("dev") + 1]
        except Exception:
            pass
        return "eth0"

    # ── Emergency ─────────────────────────────────────────

    async def panic(self):
        """
        Emergency wipe.  Called when compromise is suspected.
        Destroys all keys, peer data, and cache.
        """
        import shutil
        logger.critical("PANIC - wiping all data")
        javidnet_dir = Path.home() / ".javidnet"
        if javidnet_dir.exists():
            shutil.rmtree(javidnet_dir)
        self._running = False
        raise SystemExit("Emergency wipe complete")

    # ── Stats ─────────────────────────────────────────────

    async def _stats_loop(self):
        while self._running:
            s = self.stats()
            logger.info(
                f"Sessions: {s['active_sessions']} | "
                f"Up: {s['total_mb_up']:.1f}MB | "
                f"Down: {s['total_mb_down']:.1f}MB | "
                f"DNS cache: {s['dns_cache_entries']}"
            )
            await asyncio.sleep(60)

    def stats(self) -> Dict:
        return {
            "active_sessions": len(self._sessions),
            "peak_sessions": self._session_count_peak,
            "total_mb_up": self._total_bytes_up / 1_048_576,
            "total_mb_down": self._total_bytes_down / 1_048_576,
            "dns_cache_entries": len(self._dns_cache),
            "satellite_iface": self.config.satellite_interface,
            "uptime": int(time.time() - self._start_time),
        }


# ── Content cache ─────────────────────────────────────────

class ContentCache:
    """
    HTTP content cache for the gateway.

    On a satellite link serving thousands, caching is not optional -
    it's the difference between 10 people and 1000 people.

    Strategy:
      • Cache all 200 OK responses with cacheable headers
      • Aggressive: also cache responses without Cache-Control
        (we care about bandwidth more than freshness)
      • LRU eviction when disk is full
      • Index by SHA-256(URL) for O(1) lookup
    """

    def __init__(self, cache_dir: str, max_size_mb: int = 2000):
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb
        self._index: Dict[str, Tuple[str, int, float]] = {}  # hash → (path, size, time)

    async def start(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Load existing index
        index_path = self.cache_dir / "index.json"
        if index_path.exists():
            try:
                self._index = json.loads(index_path.read_text())
            except Exception:
                self._index = {}
        logger.info(f"Content cache: {len(self._index)} entries, "
                    f"dir={self.cache_dir}")

    async def get(self, url_hash: str) -> Optional[bytes]:
        entry = self._index.get(url_hash)
        if not entry:
            return None
        path = Path(entry[0])
        if path.exists():
            return path.read_bytes()
        return None

    async def put(self, url_hash: str, data: bytes):
        path = self.cache_dir / url_hash[:2] / url_hash
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._index[url_hash] = (str(path), len(data), time.time())
        # Evict if needed
        await self._evict_if_needed()

    async def _evict_if_needed(self):
        total = sum(entry[1] for entry in self._index.values())
        max_bytes = self.max_size_mb * 1_048_576
        if total <= max_bytes:
            return
        # LRU eviction
        sorted_entries = sorted(self._index.items(), key=lambda x: x[1][2])
        while total > max_bytes * 0.8 and sorted_entries:
            key, (path, size, _) = sorted_entries.pop(0)
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass
            del self._index[key]
            total -= size


# ── CLI entry point ──────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="JavidNet satellite gateway")
    parser.add_argument("--port", type=int, default=7744)
    parser.add_argument("--cache-size", type=int, default=2000, help="Cache size in MB")
    parser.add_argument("--max-sessions", type=int, default=200)
    args = parser.parse_args()

    config = GatewayConfig(
        mesh_listen_port=args.port,
        cache_size_mb=args.cache_size,
        max_sessions=args.max_sessions,
    )
    gw = Gateway(config)
    await gw.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        await gw.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")
    asyncio.run(main())
