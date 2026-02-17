# JavidNet

<div align="center">

```
     ██╗ █████╗ ██╗   ██╗██╗██████╗ ███╗   ██╗███████╗████████╗
     ██║██╔══██╗██║   ██║██║██╔══██╗████╗  ██║██╔════╝╚══██╔══╝
     ██║███████║██║   ██║██║██║  ██║██╔██╗ ██║█████╗     ██║
██   ██║██╔══██║╚██╗ ██╔╝██║██║  ██║██║╚██╗██║██╔══╝     ██║
╚█████╔╝██║  ██║ ╚████╔╝ ██║██████╔╝██║ ╚████║███████╗   ██║
 ╚════╝ ╚═╝  ╚═╝  ╚═══╝  ╚═╝╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝
```

**A parallel internet built from satellite dishes, mesh radios, and HF radio.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Blueprint-orange.svg)]()

</div>

**[فارسی (Persian)](README.fa.md)**

---

## What is JavidNet?

When a government shuts down the internet, circumvention tools break. VPNs, proxies, Tor bridges all depend on the government's infrastructure to carry traffic. Block the pipes, and every tool that runs inside those pipes dies.

JavidNet does not run inside the pipes.

JavidNet is a **parallel internet**, a complete replacement for the domestic network. It combines two independent communication channels:

1. **Starlink Mesh Network** - satellite dishes + local mesh radios (Wi-Fi, BLE, LoRa) for real-time internet access
2. **HF Radio Communication** - shortwave radio via ionospheric skywave for text messaging and email when even satellite is unavailable

Traffic never touches the government's infrastructure. There is nothing to block, nothing to filter, nothing to throttle.

## Architecture

![JavidNet Main Architecture](png/javid-net-Slim---Main-Architecture.png)

The system has three zones:

**Open Internet** - websites, messaging services (Signal, Telegram), email servers. Everything accessible through the global internet.

**Satellite Zone** - hidden Starlink dishes connected to gateway nodes. These are the exit points from JavidNet to the open internet. Each gateway runs a content cache, DNS resolver, traffic shaper, and bandwidth fairness system.

**Mesh Zone** - a local radio network connecting users to the nearest gateway. Users run a SOCKS5 proxy on their devices. Traffic hops across the mesh from device to device until it reaches a satellite gateway.

The government's internet is not used at any point in this chain.

## Data Flow

![JavidNet Data Flow](png/javid-net-Dataflow.png)

A single web request flows through seven steps:

1. Client encrypts request
2. Routes to internal bridge via mesh
3. Bridge forwards to Starlink gateway
4. Starlink satellite link (bypasses all domestic infrastructure)
5. Starlink receives response from internet
6. Bridge forwards response to client
7. Client decrypts response

## Exit Node Setup

![Starlink Exit Node Setup](png/javid-net-Starlink-Exit-Node-Setup.png)

Each exit node consists of a Starlink dish, a router/PC, and bridge server software. The router has two network interfaces: one connected to the Starlink dish (satellite uplink) and one connected to the domestic network (for receiving mesh traffic from users).

## Client-Side Architecture

![Client-Side Architecture](png/javid-net-Client-Side-Architecture.png)

On the user side, a custom client application (similar to Snowflake) runs on the device. It connects to the browser/app via a local proxy interface and discovers internal bridges through DHT/Gossip protocol over the domestic network.

## Protocol Layers

![Protocol Layers](png/javid-net-Protocol-Layers.png)

| Layer | Function | Technology |
|-------|----------|------------|
| 5 | Application | HTTP/HTTPS, Signal, Telegram |
| 4 | Encryption | TLS 1.3 + end-to-end encryption |
| 3 | Obfuscation | Traffic shaping, domain fronting |
| 2 | Relay | Modified Snowflake/WebRTC |
| 1 | Transport | Internal network TCP/UDP |
| 0 | Exit | Starlink to global internet |

## Two Communication Channels

### 1. Starlink Mesh Network

The primary channel. A mesh network of satellite dishes and local radios that provides real-time internet access to thousands of users simultaneously.

Three node types make up the whole system:

| Role | What it does | Hardware |
|------|-------------|----------|
| **LEAF** | End-user device. Runs SOCKS5 proxy at `127.0.0.1:1080` | Any phone/laptop/PC |
| **HOP** | Relays traffic between nodes. Extends mesh range | Any device with Wi-Fi |
| **GATEWAY** | Has a Starlink dish. Exits traffic to the real internet | RPi/PC + Starlink dish |

Full concept and design rationale: **[Starlink Mesh Network - Concept](STARLINK_MESHNETWORK_README.md)** ([فارسی](STARLINK_MESHNETWORK_README.fa.md))

Implementation source code and usage: **[starlink-meshnetwork/](starlink-meshnetwork/README.md)** ([فارسی](starlink-meshnetwork/README.fa.md))

### 2. HF Radio Communication

The backup channel. Uses shortwave radio (3-30 MHz) and ionospheric skywave propagation to send text messages and email over distances of 1000-4000 km, completely bypassing all ground-based infrastructure.

HF radio waves bounce off the ionosphere (F2 layer, ~300 km altitude) and land hundreds or thousands of kilometres away. A user in Tehran can reach Winlink email gateways in Turkey, Armenia, UAE, Kuwait, and beyond, using nothing more than a 5-10 watt radio and a thin wire antenna.

No internet is needed at the sender's location. The gateway in the neighbouring country has internet and forwards messages to their final destination.

Full details and technical diagrams: **[HF Radio Diagrams](hf-radio-diagrams/README.md)** ([فارسی](hf-radio-diagrams/README.fa.md))

## Capacity Estimates

### Starlink Mesh

| Dishes | Text/messaging | Optimised browsing | Standard browsing |
|--------|-----------------|-------------------|-------------------|
| 1 | 50,000 users | 2,000 users | 200 users |
| 5 | 250,000 users | 10,000 users | 1,000 users |
| 10 | 500,000 users | 20,000 users | 2,000 users |

These assume aggressive content optimisation and caching. Real numbers depend on usage patterns and cache hit rates.

### HF Radio

| Mode | Speed | Use case |
|------|-------|----------|
| VARA HF | 200-2000 bps | Email, short messages |
| ARDOP | 200-500 bps | Email, short messages |
| JS8Call | ~50 bps | Short text, beacon |
| FT8 | ~5 bps | Signal confirmation only |

HF radio is not a replacement for broadband. It is a lifeline for text communication when everything else is down.

## Project Structure

```
javid-net/
├── README.md                          # This file (English)
├── README.fa.md                       # This file (Farsi)
├── STARLINK_MESHNETWORK_README.md     # Starlink mesh concept & design (English)
├── STARLINK_MESHNETWORK_README.fa.md  # Starlink mesh concept & design (Farsi)
├── LICENSE                            # MIT licence
├── javid-net.drawio                   # Main architecture diagram source
├── png/                               # Main architecture diagram exports
│   ├── javid-net-Main-Architecture.png
│   ├── javid-net-Slim---Main-Architecture.png
│   ├── javid-net-Dataflow.png
│   ├── javid-net-Starlink-Exit-Node-Setup.png
│   ├── javid-net-Client-Side-Architecture.png
│   └── javid-net-Protocol-Layers.png
├── starlink-meshnetwork/              # Mesh network implementation (Python)
│   ├── README.md                      # Code-level documentation (English)
│   ├── README.fa.md                   # Code-level documentation (Farsi)
│   ├── javidnet.py                    # CLI entry point
│   ├── core/node.py                   # Mesh node, peer discovery, routing
│   ├── gateway/satellite.py           # Satellite uplink, cache, DNS, shaper
│   ├── trust/chain.py                 # Web of trust, QR onboarding
│   ├── optimizer/content.py           # Content compression & optimisation
│   ├── resilience/store_forward.py    # Queue, retry, sneakernet, wipe
│   ├── proxy/local.py                 # SOCKS5 proxy entry point
│   ├── mesh/                          # Wi-Fi, BLE, LoRa transports
│   ├── requirements.txt
│   └── diagrams/                      # Architecture diagrams
│       ├── 01-architecture.drawio
│       ├── 02-dataflow.drawio
│       ├── 03-trust-chain.drawio
│       ├── 04-optimization.drawio
│       ├── 05-resilience.drawio
│       └── png/                       # Exported diagram images
├── hf-radio-diagrams/                 # HF radio technical diagrams
│   ├── README.md                      # HF radio documentation (English)
│   ├── README.fa.md                   # HF radio documentation (Farsi)
│   ├── *.drawio                       # Diagram source files (English)
│   ├── png/                           # Exported English diagrams
│   └── farsi/                         # Farsi versions
│       ├── *.drawio                   # Diagram source files (Farsi)
│       └── png/                       # Exported Farsi diagrams
└── scripts/                           # Utility scripts
```

## Install

```bash
git clone https://github.com/user/javid-net.git
cd javid-net/starlink-meshnetwork
pip install -r requirements.txt
```

Only one required dependency: `cryptography` (for Curve25519 + Ed25519). Everything else is pure Python or optional.

## Usage

```bash
# End user (connect and browse)
python javidnet.py leaf --socks-port 1080

# Relay (help traffic reach gateways)
python javidnet.py hop

# Satellite gateway operator
python javidnet.py gateway --cache-size 2000 --max-sessions 200
```

Then configure your apps:

| App | Setting |
|-----|---------|
| Firefox | Settings > Network > Proxy > SOCKS5 `127.0.0.1:1080` |
| Chrome | `--proxy-server=socks5://127.0.0.1:1080` |
| Telegram | Settings > Data > Proxy > SOCKS5 `127.0.0.1:1080` |
| Signal | Uses system proxy |
| curl | `curl --proxy socks5h://127.0.0.1:1080 https://example.com` |

## How to Contribute

We welcome contributions from:

- **Network engineers** - protocol design, optimisation
- **Security researchers** - threat modelling, penetration testing
- **Software developers** - client/server application development
- **Hardware hackers** - antenna design, radio interface builds
- **Translators** - expanding documentation to more languages
- **Amateur radio operators** - Winlink gateway operation, HF testing

Ways to help:

1. Review the architecture and identify flaws
2. Contribute code (see starlink-meshnetwork/ for the implementation)
3. Test and report bugs
4. Build and test HF radio setups
5. Spread awareness with those who might benefit

## Disclaimer

This repository contains a **technical proposal and discussion document**. The information is for educational and research purposes.

- Implementation may be illegal in certain jurisdictions
- Users and operators assume all risks
- The authors provide no warranty and accept no liability
- Always check local laws before taking any action
- Prioritise personal safety above all else

This project is motivated by the fundamental human right to access information and communicate freely, as recognised by Article 19 of the Universal Declaration of Human Rights.

## Licence

This project is licensed under the MIT Licence. See the [LICENSE](LICENSE) file for details.

---

In darkness, one light is enough.
