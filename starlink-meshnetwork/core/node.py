"""
JavidNet — Mesh Node

The fundamental unit of JavidNet.  Every device — phone, laptop,
Raspberry Pi, router — runs a Node.  Nodes discover each other
over local radio (Wi-Fi, BLE, LoRa) and cooperate to route traffic
toward satellite gateways.

This is NOT circumvention.  The government's internet is not used
at any point.  JavidNet is a parallel network:

  Phone ──Wi-Fi──▶ Laptop ──Wi-Fi──▶ RPi ──LoRa──▶ Gateway ──Starlink──▶ Internet
    │                                                  ▲
    └──BLE──▶ Phone ──Wi-Fi──▶ Router ─────────────────┘

Roles:
  LEAF     — originates traffic (phones, laptops)
  HOP      — forwards traffic for others (any device with two+ radios)
  GATEWAY  — has a satellite dish, exits traffic to the internet

A single device can be LEAF + HOP simultaneously.
"""
import os
import time
import json
import struct
import asyncio
import hashlib
import secrets
import logging
from enum import IntFlag
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple, Callable

logger = logging.getLogger("javidnet.node")

JAVIDNET_DIR = Path.home() / ".javidnet"
KEYS_DIR = JAVIDNET_DIR / "keys"

# Protocol constants
PROTOCOL_MAGIC = b"JN"           # 2 bytes — identifies JavidNet frames
PROTOCOL_VERSION = 3
MULTICAST_GROUP = "239.77.43.1"
MESH_PORT = 7743
TUNNEL_PORT = 7744
MAX_TTL = 12                     # maximum mesh hops
BEACON_INTERVAL = 20             # seconds
PEER_TIMEOUT = 90                # drop silent peers
FRAME_MTU = 1400                 # max frame payload


class Role(IntFlag):
    LEAF = 1
    HOP = 2
    GATEWAY = 4


# ── Frame format ──────────────────────────────────────────
#
#  JavidNet frames are minimal and carry no identifying markers
#  beyond the 2-byte magic (which can be disabled for stealth mode).
#
#  Header (14 bytes):
#    [0:2]   magic     "JN"
#    [2]     version   3
#    [3]     type      BEACON=1, DATA=2, ACK=3, ROUTE=4
#    [4:12]  src_id    first 8 bytes of sender's node_id
#    [12]    ttl       remaining hops
#    [13]    flags     encrypted=0x01, compressed=0x02, priority=0x04
#  Payload:
#    [14:]   variable-length, depends on type

class FrameType:
    BEACON = 1
    DATA = 2
    ACK = 3
    ROUTE_REQUEST = 4
    ROUTE_REPLY = 5
    TRUST_VOUCH = 6
    CACHE_OFFER = 7
    SHUTDOWN = 8


@dataclass
class Peer:
    """A known mesh neighbor."""
    node_id: str                    # 16 hex chars
    public_key: bytes               # 32 bytes Curve25519
    roles: Role = Role.LEAF
    addresses: List[str] = field(default_factory=list)  # IP:port or BLE addr
    last_seen: float = 0.0
    rtt_ms: int = -1
    bandwidth_kbps: int = 0
    hops_to_gateway: int = 999
    trust: int = 0                  # 0=unknown, 1=vouched, 2=trusted, 3=operator
    voucher: str = ""               # node_id of who vouched for this peer
    link_quality: float = 1.0       # 0.0–1.0, based on packet loss


@dataclass
class RouteEntry:
    """A route toward a gateway."""
    gateway_id: str
    next_hop: str                   # node_id of next peer
    metric: float                   # lower is better
    hops: int
    bandwidth_kbps: int
    last_updated: float = 0.0
    link_quality: float = 1.0


class Node:
    """
    JavidNet mesh node.

        config = NodeConfig(roles=Role.LEAF | Role.HOP)
        node = Node(config)
        await node.start()
    """

    def __init__(self, roles: Role = Role.LEAF, mesh_port: int = MESH_PORT):
        self.roles = roles
        self.mesh_port = mesh_port
        self.node_id: str = ""
        self._private_key: bytes = b""
        self._public_key: bytes = b""
        self._peers: Dict[str, Peer] = {}
        self._routes: List[RouteEntry] = []
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._frame_handlers: Dict[int, Callable] = {}
        self._pending_acks: Dict[bytes, asyncio.Future] = {}
        self._seq = 0

        # Stats
        self._stats = {
            "frames_sent": 0, "frames_recv": 0, "frames_relayed": 0,
            "bytes_out": 0, "bytes_in": 0, "bytes_relayed": 0,
            "uptime_start": 0.0,
        }

    # ── Identity ──────────────────────────────────────────

    def init_identity(self):
        """Load or generate Curve25519 keypair."""
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        priv_path = KEYS_DIR / "node.key"
        pub_path = KEYS_DIR / "node.pub"

        if priv_path.exists() and pub_path.exists():
            self._private_key = priv_path.read_bytes()
            self._public_key = pub_path.read_bytes()
        else:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            key = X25519PrivateKey.generate()
            self._private_key = key.private_bytes_raw()
            self._public_key = key.public_key().public_bytes_raw()
            priv_path.write_bytes(self._private_key)
            pub_path.write_bytes(self._public_key)
            os.chmod(str(priv_path), 0o600)

        self.node_id = hashlib.sha256(self._public_key).hexdigest()[:16]
        logger.info(f"Node {self.node_id} [{self.roles}]")

    @property
    def src_id(self) -> bytes:
        """First 8 bytes of node_id for frame headers."""
        return bytes.fromhex(self.node_id[:16])[:8]

    # ── Lifecycle ─────────────────────────────────────────

    async def start(self):
        self.init_identity()
        self._running = True
        self._stats["uptime_start"] = time.time()

        # Register frame handlers
        self._frame_handlers = {
            FrameType.BEACON: self._on_beacon,
            FrameType.DATA: self._on_data,
            FrameType.ACK: self._on_ack,
            FrameType.ROUTE_REQUEST: self._on_route_request,
            FrameType.ROUTE_REPLY: self._on_route_reply,
            FrameType.TRUST_VOUCH: self._on_trust_vouch,
            FrameType.CACHE_OFFER: self._on_cache_offer,
        }

        # Core loops
        self._tasks.append(asyncio.create_task(self._beacon_loop()))
        self._tasks.append(asyncio.create_task(self._listen_loop()))
        self._tasks.append(asyncio.create_task(self._maintenance_loop()))

        logger.info(f"Node started on port {self.mesh_port}")

    async def stop(self):
        self._running = False
        # Broadcast shutdown
        await self._send_frame(FrameType.SHUTDOWN, b"", ttl=2)
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Node stopped")

    # ── Frame I/O ─────────────────────────────────────────

    def _build_frame(self, frame_type: int, payload: bytes,
                     ttl: int = MAX_TTL, flags: int = 0) -> bytes:
        """Build a JavidNet frame."""
        header = struct.pack(
            ">2sBB8sBB",
            PROTOCOL_MAGIC,
            PROTOCOL_VERSION,
            frame_type,
            self.src_id,
            min(ttl, MAX_TTL),
            flags,
        )
        return header + payload

    def _parse_frame(self, data: bytes) -> Optional[Tuple[int, bytes, bytes, int, int]]:
        """Parse frame → (type, src_id, payload, ttl, flags) or None."""
        if len(data) < 14:
            return None
        magic = data[0:2]
        if magic != PROTOCOL_MAGIC:
            return None
        version = data[2]
        if version != PROTOCOL_VERSION:
            return None
        frame_type = data[3]
        src_id = data[4:12]
        ttl = data[12]
        flags = data[13]
        payload = data[14:]
        return (frame_type, src_id, payload, ttl, flags)

    async def _send_frame(self, frame_type: int, payload: bytes,
                          ttl: int = MAX_TTL, flags: int = 0,
                          target_addr: Optional[Tuple[str, int]] = None):
        """Send a frame — either unicast or multicast."""
        frame = self._build_frame(frame_type, payload, ttl, flags)
        self._stats["frames_sent"] += 1
        self._stats["bytes_out"] += len(frame)

        if target_addr:
            await self._udp_send(frame, target_addr)
        else:
            await self._multicast_send(frame)

    async def _multicast_send(self, data: bytes):
        """Send to all mesh peers via UDP multicast."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.sendto(data, (MULTICAST_GROUP, self.mesh_port))
        sock.close()

    async def _udp_send(self, data: bytes, addr: Tuple[str, int]):
        """Unicast UDP send."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(data, addr)
        sock.close()

    async def _listen_loop(self):
        """Listen for incoming frames on the mesh port."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.mesh_port))

        # Join multicast group
        group = socket.inet_aton(MULTICAST_GROUP)
        mreq = struct.pack("4sL", group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)

        loop = asyncio.get_event_loop()
        while self._running:
            try:
                data, addr = await loop.run_in_executor(None, lambda: sock.recvfrom(2048))
                self._stats["frames_recv"] += 1
                self._stats["bytes_in"] += len(data)
                await self._dispatch_frame(data, addr)
            except Exception:
                await asyncio.sleep(0.1)

    async def _dispatch_frame(self, data: bytes, addr: Tuple[str, int]):
        """Route incoming frame to the right handler."""
        parsed = self._parse_frame(data)
        if not parsed:
            return
        frame_type, src_id, payload, ttl, flags = parsed

        # Ignore our own frames
        if src_id == self.src_id:
            return

        handler = self._frame_handlers.get(frame_type)
        if handler:
            await handler(src_id, payload, ttl, flags, addr)

    # ── Beacons (peer discovery) ──────────────────────────

    async def _beacon_loop(self):
        """Periodically announce ourselves to the mesh."""
        while self._running:
            await self._send_beacon()
            await asyncio.sleep(BEACON_INTERVAL + secrets.randbelow(5))

    async def _send_beacon(self):
        """
        Beacon payload:
          { "id": "a1b2...", "pk": "<hex>", "r": 5, "h": 2, "bw": 50000 }

        Compact: ~120 bytes.  Fits in a single UDP packet,
        a BLE advertisement, or a LoRa frame.
        """
        beacon = {
            "id": self.node_id,
            "pk": self._public_key.hex(),
            "r": int(self.roles),
            "h": self._my_gateway_distance(),
            "bw": self._advertised_bandwidth(),
        }
        payload = json.dumps(beacon, separators=(",", ":")).encode()
        await self._send_frame(FrameType.BEACON, payload, ttl=3)

    async def _on_beacon(self, src_id, payload, ttl, flags, addr):
        """Handle incoming beacon — update peer table."""
        try:
            b = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        peer_id = b.get("id", "")
        if not peer_id or peer_id == self.node_id:
            return

        existing = self._peers.get(peer_id)
        peer = Peer(
            node_id=peer_id,
            public_key=bytes.fromhex(b.get("pk", "")),
            roles=Role(b.get("r", 1)),
            addresses=[f"{addr[0]}:{addr[1]}"],
            last_seen=time.time(),
            hops_to_gateway=b.get("h", 999),
            bandwidth_kbps=b.get("bw", 0),
            trust=existing.trust if existing else 0,
            voucher=existing.voucher if existing else "",
        )
        self._peers[peer_id] = peer
        self._rebuild_routes()

    # ── Routing ───────────────────────────────────────────
    #
    #  JavidNet uses a distance-vector approach optimized for
    #  the specific problem: find the best path to a GATEWAY.
    #
    #  Metric = hops × (1/link_quality) × (1/bandwidth_weight)
    #
    #  This is NOT BGP, NOT OSPF, NOT Babel.  It's purpose-built
    #  for a mesh where the only destination that matters is
    #  "the nearest satellite dish."

    def _rebuild_routes(self):
        """Recalculate routes to all known gateways."""
        self._routes = []

        for peer_id, peer in self._peers.items():
            if peer.trust < 1:
                continue  # don't route through unknown peers

            if Role.GATEWAY & peer.roles:
                # Direct route to a gateway
                metric = self._route_metric(peer, direct=True)
                self._routes.append(RouteEntry(
                    gateway_id=peer_id,
                    next_hop=peer_id,
                    metric=metric,
                    hops=1,
                    bandwidth_kbps=peer.bandwidth_kbps,
                    last_updated=time.time(),
                    link_quality=peer.link_quality,
                ))
            elif peer.hops_to_gateway < MAX_TTL:
                # Indirect route — this peer can reach a gateway
                metric = self._route_metric(peer, direct=False)
                self._routes.append(RouteEntry(
                    gateway_id=f"via:{peer_id}",
                    next_hop=peer_id,
                    metric=metric,
                    hops=peer.hops_to_gateway + 1,
                    bandwidth_kbps=min(peer.bandwidth_kbps, 10_000),
                    last_updated=time.time(),
                    link_quality=peer.link_quality,
                ))

        # Sort by metric (lower = better)
        self._routes.sort(key=lambda r: r.metric)

    def _route_metric(self, peer: Peer, direct: bool) -> float:
        """
        Compute route metric.  Lower is better.

        Factors:
          - hops (each hop adds latency and failure risk)
          - link quality (packet loss degrades throughput)
          - bandwidth (prefer fat links)
          - trust (prefer trusted paths)
        """
        hops = 1 if direct else (peer.hops_to_gateway + 1)
        lq = max(peer.link_quality, 0.01)
        bw = max(peer.bandwidth_kbps, 1)
        trust_bonus = 1.0 - (peer.trust * 0.1)  # trusted peers get lower metric

        return (hops / lq) * (10_000 / bw) * trust_bonus

    def best_route(self) -> Optional[RouteEntry]:
        """Return the best available route to any gateway."""
        for route in self._routes:
            peer = self._peers.get(route.next_hop)
            if peer and time.time() - peer.last_seen < PEER_TIMEOUT:
                return route
        return None

    def _my_gateway_distance(self) -> int:
        """Our hop distance to the nearest gateway."""
        if Role.GATEWAY & self.roles:
            return 0
        route = self.best_route()
        return route.hops if route else 999

    def _advertised_bandwidth(self) -> int:
        """Bandwidth we advertise in beacons (KB/s)."""
        if Role.GATEWAY & self.roles:
            return 50_000  # ~50 MB/s Starlink
        return 5_000       # ~5 MB/s Wi-Fi relay

    # ── Data forwarding ───────────────────────────────────

    async def _on_data(self, src_id, payload, ttl, flags, addr):
        """
        Handle incoming data frame.
        If we're the destination → deliver to local apps.
        If not → forward toward gateway (decrement TTL).
        """
        if ttl <= 0:
            return  # expired

        # Check if this data is for us
        if len(payload) < 8:
            return
        dest_id = payload[:8]

        if dest_id == self.src_id:
            # For us — deliver to tunnel layer
            await self._deliver_local(payload[8:], flags)
        elif Role.HOP & self.roles or Role.GATEWAY & self.roles:
            # Relay — forward toward gateway
            route = self.best_route()
            if route:
                peer = self._peers.get(route.next_hop)
                if peer and peer.addresses:
                    next_addr = self._parse_addr(peer.addresses[0])
                    new_frame = self._build_frame(
                        FrameType.DATA, payload, ttl=ttl - 1, flags=flags,
                    )
                    await self._udp_send(new_frame, next_addr)
                    self._stats["frames_relayed"] += 1
                    self._stats["bytes_relayed"] += len(payload)

    async def send_to_gateway(self, data: bytes) -> bool:
        """
        Send data through the mesh toward the best gateway.
        Returns True if the frame was sent (not necessarily delivered).
        """
        route = self.best_route()
        if not route:
            return False

        peer = self._peers.get(route.next_hop)
        if not peer or not peer.addresses:
            return False

        # Frame payload: [dest_id(8)] [data]
        # dest_id = 0x00*8 means "any gateway"
        dest_id = b"\x00" * 8
        payload = dest_id + data
        next_addr = self._parse_addr(peer.addresses[0])
        await self._send_frame(FrameType.DATA, payload, target_addr=next_addr)
        return True

    async def _deliver_local(self, data: bytes, flags: int):
        """Deliver received data to local applications."""
        # Decrypt if needed
        if flags & 0x01:
            data = await self._decrypt(data)
        # Decompress if needed
        if flags & 0x02:
            import zlib
            data = zlib.decompress(data)
        # Hand off to the tunnel/proxy layer
        # (Connected via callback or queue)
        logger.debug(f"Received {len(data)} bytes for local delivery")

    # ── Route discovery ───────────────────────────────────

    async def _on_route_request(self, src_id, payload, ttl, flags, addr):
        """
        Someone is looking for a gateway.
        If we know one, reply.  Otherwise, rebroadcast (with lower TTL).
        """
        if Role.GATEWAY & self.roles:
            # We ARE a gateway — reply directly
            reply = {
                "gw": self.node_id,
                "h": 0,
                "bw": self._advertised_bandwidth(),
            }
            reply_data = json.dumps(reply, separators=(",", ":")).encode()
            await self._send_frame(
                FrameType.ROUTE_REPLY, reply_data,
                target_addr=addr,
            )
        elif self._routes:
            # We know a route — reply with our best
            best = self._routes[0]
            reply = {
                "gw": best.gateway_id,
                "h": best.hops + 1,
                "bw": best.bandwidth_kbps,
                "via": self.node_id,
            }
            reply_data = json.dumps(reply, separators=(",", ":")).encode()
            await self._send_frame(
                FrameType.ROUTE_REPLY, reply_data,
                target_addr=addr,
            )
        elif ttl > 1:
            # Rebroadcast the request
            await self._send_frame(FrameType.ROUTE_REQUEST, payload, ttl=ttl - 1)

    async def _on_route_reply(self, src_id, payload, ttl, flags, addr):
        """Process a route reply — add gateway to our routing table."""
        try:
            r = json.loads(payload)
        except Exception:
            return
        via_peer = r.get("via", src_id.hex()[:16])
        peer = self._peers.get(via_peer)
        if not peer:
            return

        self._routes.append(RouteEntry(
            gateway_id=r.get("gw", "unknown"),
            next_hop=via_peer,
            metric=self._route_metric(peer, direct=False),
            hops=r.get("h", 999),
            bandwidth_kbps=r.get("bw", 0),
            last_updated=time.time(),
        ))
        self._routes.sort(key=lambda r: r.metric)
        logger.info(f"Route discovered: gateway {r.get('gw')} via {via_peer}, {r.get('h')} hops")

    async def discover_gateways(self):
        """Actively search for gateways by flooding a ROUTE_REQUEST."""
        req = {"src": self.node_id, "ts": int(time.time())}
        payload = json.dumps(req, separators=(",", ":")).encode()
        await self._send_frame(FrameType.ROUTE_REQUEST, payload, ttl=MAX_TTL)
        logger.info("Gateway discovery broadcast sent")

    # ── Trust / vouching ──────────────────────────────────

    async def _on_trust_vouch(self, src_id, payload, ttl, flags, addr):
        """
        A trusted peer vouches for another peer.
        Trust chain: operator → trusted → vouched → unknown
        """
        try:
            v = json.loads(payload)
        except Exception:
            return

        voucher_id = v.get("from", "")
        target_id = v.get("for", "")
        voucher = self._peers.get(voucher_id)

        if not voucher or voucher.trust < 2:
            return  # only trusted+ peers can vouch

        target = self._peers.get(target_id)
        if target and target.trust < voucher.trust:
            target.trust = min(voucher.trust - 1, 2)
            target.voucher = voucher_id
            logger.info(f"Peer {target_id} vouched by {voucher_id} → trust={target.trust}")

    async def vouch_for(self, peer_id: str):
        """Vouch for a peer — grant them trust based on our own level."""
        vouch = {"from": self.node_id, "for": peer_id, "ts": int(time.time())}
        payload = json.dumps(vouch, separators=(",", ":")).encode()
        await self._send_frame(FrameType.TRUST_VOUCH, payload, ttl=3)

    # ── Cache offers ──────────────────────────────────────

    async def _on_cache_offer(self, src_id, payload, ttl, flags, addr):
        """
        A peer announces cached content.
        This is JavidNet's bandwidth multiplier: if 100 people want
        the same news article, only one copy crosses the satellite link.
        """
        try:
            offer = json.loads(payload)
        except Exception:
            return
        # Store in local cache index
        # offer = {"urls": ["hash1", "hash2"], "node": "abc123"}
        logger.debug(f"Cache offer from {offer.get('node')}: {len(offer.get('urls', []))} items")

    # ── ACKs ──────────────────────────────────────────────

    async def _on_ack(self, src_id, payload, ttl, flags, addr):
        """Process acknowledgment for reliable delivery."""
        if len(payload) >= 4:
            seq = struct.unpack(">I", payload[:4])[0]
            fut = self._pending_acks.pop(seq, None)
            if fut and not fut.done():
                fut.set_result(True)

    # ── Maintenance ───────────────────────────────────────

    async def _maintenance_loop(self):
        """Periodic cleanup: expire peers, probe link quality, etc."""
        while self._running:
            now = time.time()
            # Expire stale peers
            stale = [pid for pid, p in self._peers.items()
                     if now - p.last_seen > PEER_TIMEOUT]
            for pid in stale:
                del self._peers[pid]
            if stale:
                self._rebuild_routes()

            # If we have no routes, actively search
            if not self._routes and not (Role.GATEWAY & self.roles):
                await self.discover_gateways()

            await asyncio.sleep(30)

    # ── Helpers ───────────────────────────────────────────

    def _parse_addr(self, addr_str: str) -> Tuple[str, int]:
        """Parse 'ip:port' string."""
        parts = addr_str.rsplit(":", 1)
        return (parts[0], int(parts[1]) if len(parts) > 1 else self.mesh_port)

    async def _decrypt(self, data: bytes) -> bytes:
        """Decrypt incoming data (placeholder — see tunnel module)."""
        return data  # actual decryption in tunnel layer

    # ── Status ────────────────────────────────────────────

    def status(self) -> Dict:
        route = self.best_route()
        return {
            "node_id": self.node_id,
            "roles": str(self.roles),
            "peers": len(self._peers),
            "trusted_peers": sum(1 for p in self._peers.values() if p.trust >= 1),
            "gateways_known": sum(1 for r in self._routes
                                  if not r.gateway_id.startswith("via:")),
            "best_route_hops": route.hops if route else -1,
            "best_route_bw": route.bandwidth_kbps if route else 0,
            **self._stats,
            "uptime": int(time.time() - self._stats["uptime_start"]),
        }


# ── CLI entry point ──────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="JavidNet mesh node")
    parser.add_argument("--role", choices=["leaf", "hop", "gateway"], default="leaf")
    parser.add_argument("--port", type=int, default=MESH_PORT)
    args = parser.parse_args()

    role_map = {"leaf": Role.LEAF, "hop": Role.LEAF | Role.HOP,
                "gateway": Role.LEAF | Role.HOP | Role.GATEWAY}
    node = Node(roles=role_map[args.role], mesh_port=args.port)
    await node.start()

    try:
        while True:
            await asyncio.sleep(60)
            s = node.status()
            logger.info(f"Status: {s['peers']} peers, {s['gateways_known']} gateways, "
                        f"route: {s['best_route_hops']} hops")
    except KeyboardInterrupt:
        await node.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")
    asyncio.run(main())
