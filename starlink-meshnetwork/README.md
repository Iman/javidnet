# JavidNet - Implementation

```
     ██╗ █████╗ ██╗   ██╗██╗██████╗ ███╗   ██╗███████╗████████╗
     ██║██╔══██╗██║   ██║██║██╔══██╗████╗  ██║██╔════╝╚══██╔══╝
     ██║███████║██║   ██║██║██║  ██║██╔██╗ ██║█████╗     ██║
██   ██║██╔══██║╚██╗ ██╔╝██║██║  ██║██║╚██╗██║██╔══╝     ██║
╚█████╔╝██║  ██║ ╚████╔╝ ██║██████╔╝██║ ╚████║███████╗   ██║
 ╚════╝ ╚═╝  ╚═╝  ╚═══╝  ╚═╝╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝
```

**Python implementation of the JavidNet parallel internet mesh network.**

[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Blueprint-orange.svg)]()

**[فارسی (Persian)](README.fa.md)**

---

## Modules

```
starlink-meshnetwork/
├── javidnet.py              # CLI entry point
├── core/
│   └── node.py              # Mesh node: peer discovery, routing, beacons
├── gateway/
│   └── satellite.py         # Satellite uplink: dish management, cache, DNS
├── trust/
│   └── chain.py             # Web of trust: QR onboarding, vouch chains
├── optimizer/
│   └── content.py           # Bandwidth multiplier: compress, cache, prioritise
├── resilience/
│   └── store_forward.py     # Degradation: queue, retry, sneakernet, wipe
├── proxy/
│   └── local.py             # SOCKS5 proxy: entry point for user apps
├── mesh/
│   └── (transports)         # Wi-Fi, BLE, LoRa mesh transports
├── requirements.txt
└── diagrams/
    ├── 01-architecture.drawio
    ├── 02-dataflow.drawio
    ├── 03-trust-chain.drawio
    ├── 04-optimization.drawio
    ├── 05-resilience.drawio
    └── png/                 # Exported diagram images
```

## Install

```bash
git clone https://github.com/user/javid-net.git
cd javid-net/starlink-meshnetwork
pip install -r requirements.txt
```

Only one required dependency: `cryptography` (for Curve25519 + Ed25519). Everything else is pure Python or optional.

Optional: `Pillow>=10.0` for image transcoding (WebP, resize). Without Pillow, images are compressed with gzip only.

## Usage

### End user (LEAF)

```bash
python javidnet.py leaf --socks-port 1080
```

Then configure your apps:

| App | Setting |
|-----|---------|
| Firefox | Settings > Network > Proxy > SOCKS5 `127.0.0.1:1080` |
| Chrome | `--proxy-server=socks5://127.0.0.1:1080` |
| Telegram | Settings > Data > Proxy > SOCKS5 `127.0.0.1:1080` |
| Signal | Uses system proxy |
| curl | `curl --proxy socks5h://127.0.0.1:1080 https://example.com` |

### Relay (HOP)

Help the mesh reach further. Any device can be a hop:

```bash
python javidnet.py hop
```

### Satellite gateway (GATEWAY)

Requires a Starlink dish. This is the internet exit:

```bash
python javidnet.py gateway --cache-size 2000 --max-sessions 200
```

## Architecture

![System Architecture](diagrams/png/01-architecture-System-Architecture.png)

Three node types. That is the whole system.

| Role | What it does | Hardware |
|------|-------------|----------|
| **LEAF** | End-user device. Runs SOCKS5 proxy at `127.0.0.1:1080`. Apps connect here. | Any phone/laptop/PC |
| **HOP** | Relays traffic between nodes. Extends mesh range. | Any device with Wi-Fi |
| **GATEWAY** | Has a Starlink dish. Exits traffic to the real internet. | RPi/PC + Starlink dish |

A LEAF's traffic hops across the mesh from device to device until it reaches a GATEWAY, which sends it to the internet via satellite.

## Data Flow

![Data Flow](diagrams/png/02-dataflow-Data-Flow.png)

Each frame has a 14-byte header:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0:2 | 2 bytes | magic | `JN` (identifies JavidNet frames) |
| 2 | 1 byte | version | Protocol version (currently 3) |
| 3 | 1 byte | type | BEACON=1, DATA=2, ACK=3, ROUTE=4, etc. |
| 4:12 | 8 bytes | src_id | First 8 bytes of sender's node_id |
| 12 | 1 byte | ttl | Remaining hops (max 12) |
| 13 | 1 byte | flags | encrypted=0x01, compressed=0x02, priority=0x04 |

Mesh port: 7743, Tunnel port: 7744, SOCKS5: 1080.

## Trust Model

![Trust Chain](diagrams/png/03-trust-chain-Trust-Chain.png)

No central authority. Trust spreads person-to-person:

```
 OPERATOR (runs a dish)
    |
    | vouches in person
    v
 TRUSTED (can vouch others)
    |
    | vouches in person
    v
 VOUCHED (can use the network)
    |
    x cannot vouch anyone
```

**Onboarding:** Meet an existing member. They scan your QR code. You are in. No app store, no SMS, no email. One camera, one screen.

QR code format: `javidnet://<node_id>/<pubkey_hex>`

**Revocation cascades:** If a member is compromised, everyone they vouched for is also revoked.

Trust data stored in SQLite (`~/.javidnet/trust.db`) with tables: `peers`, `vouches`, `revocations`.

## Content Optimisation

![Content Optimisation](diagrams/png/04-optimization-Content-Optimization.png)

With 5 Starlink dishes serving a city, every byte counts.

| Bandwidth mode | What gets through | Who it helps |
|----------------|-------------------|--------------|
| **CRISIS** | Text only. No images, no JS, no video. | 250,000 users messaging |
| **TIGHT** | Text + tiny images (200px, 30% quality). No JS. | 10,000 users browsing |
| **NORMAL** | Compressed browsing. Images at 800px. | 2,000 users browsing |
| **GENEROUS** | Light compression. Near-normal experience. | 1,000 users |

The gateway's content cache (SHA-256 indexed, LRU eviction, 2 TB default) is the bandwidth multiplier. When 10,000 people want the same article, only one copy crosses the satellite link.

## Resilience

![Resilience](diagrams/png/05-resilience-Resilience---Degradation.png)

| Level | Condition | JavidNet does... |
|-------|-----------|-----------------|
| **FULL** | Satellite up | Normal operation |
| **DEGRADED** | Satellite intermittent | Queue + auto-retry |
| **MESH_ONLY** | No satellite | Local mesh messaging works, internet queued |
| **SNEAKERNET** | No mesh | Export to USB, physically carry to another gateway |

Messages are never lost. They wait in a persistent queue (SQLite, `~/.javidnet/queue.db`) and drain automatically when connectivity returns.

**Emergency wipe:** If physical compromise is suspected, one command destroys all keys, peer data, trust chains, and cache (`~/.javidnet/` directory removed).

## Capacity Estimate

| Dishes | Text/messaging | Optimised browsing | Standard browsing |
|--------|-----------------|-------------------|-------------------|
| 1 | 50,000 users | 2,000 users | 200 users |
| 5 | 250,000 users | 10,000 users | 1,000 users |
| 10 | 500,000 users | 20,000 users | 2,000 users |

These assume aggressive content optimisation and caching. Real numbers depend on usage patterns and cache hit rates.

## Conceptual Documentation

For the full design rationale, comparisons with circumvention tools, and non-code documentation, see [STARLINK_MESHNETWORK_README.md](../STARLINK_MESHNETWORK_README.md) in the project root.

---

In darkness, one light is enough.
