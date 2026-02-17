# JavidNet - Starlink Mesh Network

**A parallel internet built from satellite dishes and mesh radios.**

[![Status](https://img.shields.io/badge/Status-Blueprint-orange.svg)]()

**[فارسی (Persian)](STARLINK_MESHNETWORK_README.fa.md)**

---

## The Concept

When a government shuts down the internet, circumvention tools break. VPNs, proxies, Tor bridges all depend on the government's infrastructure to carry traffic. Block the pipes, and every tool that runs inside those pipes dies.

JavidNet does not run inside the pipes.

JavidNet is a **parallel internet**, a complete replacement for the domestic network, built from Starlink satellite dishes and local mesh radios. Traffic never touches the government's infrastructure. There is nothing to block, nothing to filter, nothing to throttle.

```
  Circumvention tools:
    Phone > [Government's Internet] > VPN/Tor > Web
              ^
              | they shut this down
              \-- everything breaks

  JavidNet:
    Phone > [Mesh Radio] > [Starlink Dish] > Web
              ^
              | government's internet not involved
              \-- nothing to shut down
```

## System Architecture

![System Architecture](starlink-meshnetwork/diagrams/png/01-architecture-System-Architecture.png)

The architecture has three zones:

**Open Internet** - websites, messaging services (Signal, Telegram), news, search engines, email. Accessible via Starlink satellite uplink. DNS is resolved through Cloudflare DoH (1.1.1.1), never through domestic resolvers.

**Satellite Zone** - hidden Starlink dishes connected to GATEWAY nodes. Each gateway runs:
- Satellite uplink management (`gateway/satellite.py`)
- Content cache (2 TB disk, LRU, SHA-256 indexed)
- Content optimiser (`optimizer/content.py`) for compression and transcoding
- Bandwidth fairness (token bucket per session, priority CRITICAL to BULK)
- DNS resolver (DoH to 1.1.1.1, cached with 5 min TTL)
- Panic wipe (destroy all data on suspected compromise)

**Mesh Zone** - local radio network of HOP and LEAF nodes. HOPs relay traffic using Wi-Fi, BLE, or LoRa. LEAFs are end-user devices running a SOCKS5 proxy at `127.0.0.1:1080`. Traffic hops across the mesh until it reaches a GATEWAY.

The government's internet is not used at any point.

**Port assignments:** Mesh: 7743 | Tunnel: 7744 | SOCKS5: 1080 | DNS: 5353

## Data Flow

![Data Flow](starlink-meshnetwork/diagrams/png/02-dataflow-Data-Flow.png)

A web request flows through these stages:

1. App sends request to local SOCKS5 proxy (127.0.0.1:1080)
2. Proxy encrypts and sends to the mesh node (`core/node.py`)
3. Mesh node routes through HOPs toward a GATEWAY
4. GATEWAY checks content cache - if cached, returns immediately
5. If not cached, GATEWAY fetches from internet via Starlink satellite
6. Response is optimised (compressed, images transcoded, scripts stripped based on bandwidth mode)
7. Optimised response sent back through mesh to the user

Encryption at each point: Curve25519 + ChaCha20 between mesh peers, TLS 1.3 to the open internet.

## Node Types

Three node types make up the whole system:

| Role | What it does | Hardware |
|------|-------------|----------|
| **LEAF** | End-user device. Runs SOCKS5 proxy at `127.0.0.1:1080`. Apps connect here. | Any phone/laptop/PC |
| **HOP** | Relays traffic between nodes. Extends mesh range. | Any device with Wi-Fi |
| **GATEWAY** | Has a Starlink dish. Exits traffic to the real internet. | RPi/PC + Starlink dish |

A single device can be LEAF + HOP simultaneously.

**Key design decisions:**

- **No onion routing.** The entire network is invisible to the state because traffic never enters their infrastructure. Anonymity layers are unnecessary overhead.
- **No pluggable transports.** Nothing to disguise, there is no DPI to evade because there is no government backbone to inspect.
- **No directory servers.** Peers discover each other via local radio beacons (UDP multicast, BLE, LoRa).
- **No certificates.** Trust is built through physical verification - scan a QR code in person to join the network.

## Trust Chain Model

![Trust Chain](starlink-meshnetwork/diagrams/png/03-trust-chain-Trust-Chain.png)

JavidNet has no central authority. Trust spreads person-to-person through a web of trust:

**Trust levels:**

| Level | Name | How you get it | What you can do |
|-------|------|---------------|-----------------|
| 3 | OPERATOR | Run a satellite gateway dish | Vouch others up to TRUSTED |
| 2 | TRUSTED | Vouched by an OPERATOR | Vouch others up to VOUCHED, relay traffic |
| 1 | VOUCHED | Vouched by a TRUSTED peer | Use the network |
| 0 | UNKNOWN | Default state | Can see beacons but cannot route traffic |

**Onboarding flow:**

1. New user installs JavidNet, generates Curve25519 keypair, trust = 0
2. Meets an existing member in person (physical proximity required)
3. Existing member scans new user's QR code (contains public key)
4. Member signs a vouch with Ed25519: "I vouch for &lt;pubkey&gt;"
5. New user is now trust = 1, can use the network

This is intentionally slow. Speed equals infiltration risk. Every vouch is a personal guarantee.

**Revocation cascades:** If a member is compromised, everyone they vouched for is also revoked. This makes infiltration expensive, because one bad actor takes down their entire branch.

## Content Optimisation and Bandwidth Modes

![Content Optimisation](starlink-meshnetwork/diagrams/png/04-optimization-Content-Optimization.png)

With 5 Starlink dishes serving a city, every byte counts. The content optimiser processes HTTP responses before sending them through the satellite link:

| Bandwidth mode | What gets through | Who it helps |
|----------------|-------------------|--------------|
| **CRISIS** | Text only. No images, no JS, no video. | 250,000 users messaging |
| **TIGHT** | Text + tiny images (200px, 30% quality). No JS. | 10,000 users browsing |
| **NORMAL** | Compressed browsing. Images at 800px, 60% quality. | 2,000 users browsing |
| **GENEROUS** | Light compression. Near-normal experience. | 1,000 users |

**Optimisation pipeline:**
1. **Compress** - gzip/brotli all text content
2. **Transcode** - downscale images (2MB JPEG to 40KB WebP), strip video
3. **Dedup** - if 100 people request BBC Persian, fetch it once (SHA-256 URL hash)
4. **Prefetch** - predict popular content, cache ahead
5. **Prioritise** - text first, images later, video only if bandwidth allows

**Traffic priority classes:** CRITICAL (DNS, control) > INTERACTIVE (chat, messaging) > STANDARD (browsing) > BULK (downloads) > BACKGROUND (cache prefetch)

The gateway's content cache is the bandwidth multiplier. When 10,000 people want the same article, only one copy crosses the satellite link.

## Resilience and Degradation

![Resilience and Degradation](starlink-meshnetwork/diagrams/png/05-resilience-Resilience---Degradation.png)

What happens when things go wrong?

| Level | Condition | JavidNet does... |
|-------|-----------|-----------------|
| **FULL** | Satellite up | Normal operation |
| **DEGRADED** | Satellite intermittent | Queue + auto-retry |
| **MESH_ONLY** | No satellite | Local mesh messaging works, internet queued |
| **SNEAKERNET** | No mesh | Export to USB, physically carry to another gateway |

Messages are never lost. They wait in a persistent queue (SQLite database) and drain automatically when connectivity returns.

**Store and forward:** When the satellite is down, outbound requests are queued to disk. When connectivity returns, the queue drains automatically in priority order. Messages have configurable TTL (default 72 hours) and max retry attempts.

**Sneakernet:** If all gateways in your city go down, export your queued messages to a USB stick. Physically carry it to a city where gateways work. Import the messages there, and they drain through that gateway's satellite link.

**Emergency wipe:** If physical compromise is suspected, one command destroys all keys, peer data, trust chains, message queue, and cache.

## Why Not Circumvention?

| | Circumvention (VPN/Tor) | JavidNet |
|---|---|---|
| **Uses government's internet** | Yes | No |
| **Breaks during shutdown** | Yes | No |
| **Can be DPI'd** | Yes | N/A, no government traffic |
| **Needs bridges/relays abroad** | Yes | No |
| **Works with zero domestic internet** | No | Yes |
| **Requires physical hardware** | No | Yes (dishes) |
| **Scales to 50K+ users** | Varies | With caching, yes |

JavidNet is not better or worse than circumvention. It solves a **different problem**: what happens when circumvention is impossible because the internet itself does not exist.

## Capacity Estimate

| Dishes | Text/messaging | Optimised browsing | Standard browsing |
|--------|-----------------|-------------------|-------------------|
| 1 | 50,000 users | 2,000 users | 200 users |
| 5 | 250,000 users | 10,000 users | 1,000 users |
| 10 | 500,000 users | 20,000 users | 2,000 users |

These assume aggressive content optimisation and caching. Real numbers depend on usage patterns and cache hit rates.

**Starlink specifications assumed:** ~100 Mbps download, ~20 Mbps upload per dish. Actual Starlink performance varies by location, congestion, and weather (typically 50-200 Mbps down, 10-20 Mbps up).

## Implementation

The Python implementation is in the `starlink-meshnetwork/` directory. See [starlink-meshnetwork/README.md](starlink-meshnetwork/README.md) for code documentation, installation, and usage instructions.

---

In darkness, one light is enough.
