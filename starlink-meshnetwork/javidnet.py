"""
JavidNet — CLI Entry Point

Start JavidNet in one of three modes:

  $ javidnet leaf          # End user — connect and browse
  $ javidnet hop           # Relay — help others reach gateways
  $ javidnet gateway       # Operator — run a satellite exit

"""
import asyncio
import argparse
import logging
import signal

from core.node import Node, Role, MESH_PORT
from proxy.local import LocalProxy
from resilience.store_forward import ResilienceManager

logger = logging.getLogger("javidnet")


async def run_leaf(args):
    """Start as a leaf node with local SOCKS5 proxy."""
    node = Node(roles=Role.LEAF, mesh_port=args.port)
    await node.start()

    # Discover gateways
    await node.discover_gateways()

    # Start local proxy
    async def connect_via_mesh(host, port):
        route = node.best_route()
        if not route:
            raise ConnectionError("No gateway reachable — check mesh connectivity")
        peer = node._peers.get(route.next_hop)
        addr = node._parse_addr(peer.addresses[0])
        return await asyncio.open_connection(addr[0], 7744)

    proxy = LocalProxy(port=args.socks_port, connect_fn=connect_via_mesh)
    proxy_task = asyncio.create_task(proxy.serve())

    logger.info(f"JavidNet leaf running — SOCKS5 proxy on 127.0.0.1:{args.socks_port}")
    logger.info(f"Configure your apps: SOCKS5 → 127.0.0.1:{args.socks_port}")

    try:
        while True:
            await asyncio.sleep(30)
            s = node.status()
            logger.info(f"Peers: {s['peers']} | Gateways: {s['gateways_known']} | "
                        f"Route: {s['best_route_hops']} hops")
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()


async def run_hop(args):
    """Start as a relay (hop) node — forward traffic for others."""
    node = Node(roles=Role.LEAF | Role.HOP, mesh_port=args.port)
    await node.start()

    logger.info("JavidNet hop running — relaying traffic for the mesh")

    try:
        while True:
            await asyncio.sleep(60)
            s = node.status()
            logger.info(f"Peers: {s['peers']} | Relayed: {s['bytes_relayed']} bytes | "
                        f"Gateways: {s['gateways_known']}")
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()


async def run_gateway(args):
    """Start as a satellite gateway — the internet exit."""
    from gateway.satellite import Gateway, GatewayConfig

    # Start mesh node with GATEWAY role
    node = Node(roles=Role.LEAF | Role.HOP | Role.GATEWAY, mesh_port=args.port)
    await node.start()

    # Start gateway
    config = GatewayConfig(
        mesh_listen_port=args.port + 1,
        cache_size_mb=args.cache_size,
        max_sessions=args.max_sessions,
    )
    gw = Gateway(config)
    await gw.start()

    # Start resilience manager
    resilience = ResilienceManager()
    await resilience.start()

    logger.info(f"JavidNet GATEWAY running — mesh:{args.port}, tunnels:{args.port + 1}")

    try:
        while True:
            await asyncio.sleep(60)
            ns = node.status()
            gs = gw.stats()
            logger.info(
                f"Peers: {ns['peers']} | Sessions: {gs['active_sessions']} | "
                f"Up: {gs['total_mb_up']:.1f}MB | Down: {gs['total_mb_down']:.1f}MB"
            )
    except asyncio.CancelledError:
        pass
    finally:
        await gw.stop()
        await node.stop()


def main():
    parser = argparse.ArgumentParser(
        prog="javidnet",
        description="JavidNet — parallel internet via satellite mesh",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # Leaf
    leaf = sub.add_parser("leaf", help="End user — browse via JavidNet")
    leaf.add_argument("--port", type=int, default=MESH_PORT, help="Mesh port")
    leaf.add_argument("--socks-port", type=int, default=1080, help="Local SOCKS5 port")

    # Hop
    hop = sub.add_parser("hop", help="Relay — help traffic reach gateways")
    hop.add_argument("--port", type=int, default=MESH_PORT, help="Mesh port")

    # Gateway
    gw = sub.add_parser("gateway", help="Operator — satellite internet exit")
    gw.add_argument("--port", type=int, default=MESH_PORT, help="Mesh port")
    gw.add_argument("--cache-size", type=int, default=2000, help="Cache size MB")
    gw.add_argument("--max-sessions", type=int, default=200, help="Max concurrent users")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    loop = asyncio.new_event_loop()

    # Handle graceful shutdown
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: loop.stop())

    if args.mode == "leaf":
        loop.run_until_complete(run_leaf(args))
    elif args.mode == "hop":
        loop.run_until_complete(run_hop(args))
    elif args.mode == "gateway":
        loop.run_until_complete(run_gateway(args))


if __name__ == "__main__":
    main()
