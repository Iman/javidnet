# Security Policy

## Report privately. Always.

Report a security problem through GitHub private vulnerability reporting. Open
the Security tab of this repository and select "Report a vulnerability". That
opens a thread only the maintainer can read. If that route is not open to you,
use the contact route on the project's GitHub page.

Do not open a public issue, a pull request, a discussion post, or a social media
thread first.

The reason is the shape of this project. JavidNet is not a piece of software
that runs on a server somewhere. It is a description of a network made of
people, radios, and satellite dishes, and the people are the part that cannot be
patched. A flaw published here is read by the party those people are hiding
from, and it is read the same day. What they do with it is not a software
exploit. It is a search for a dish, a radio, or a name.

There is a second reason particular to this repository. Most of it is a
blueprint. A public report of a flaw in a design that nobody has built yet gives
away the design's weak point before anyone can fix it, and buys the users
nothing, because there is no deployment to protect.

## The threat model

The attacker cannot do the usual thing. JavidNet does not run inside the
domestic network, so blocking a port, poisoning a resolver, or throttling a
protocol reaches none of it. That is the point of the design, and it pushes the
attacker onto three other routes.

**Find the hardware.** A Starlink dish is a physical object with a distinctive
outline and a distinctive uplink emission. An HF antenna is a wire, and an HF
transmitter can be located by direction finding while it is transmitting. The
gateways are the scarcest thing in the whole system: the capacity table assumes
between one and ten dishes for an entire city. Losing one gateway removes
service for everybody routed through it. This is the attack with the best return
and it needs no software knowledge at all.

**Find a node by what it emits.** A JavidNet node beacons every 20 seconds to
multicast group `239.77.43.1` on port `7743`, and every frame begins with the
constant bytes `JN`. Anyone within radio range receives that, including someone
who simply joins the same Wi-Fi. The frame carries the sender's role. A beacon
that announces GATEWAY is a direction-finding target that identified itself.

**Get inside the trust graph.** Onboarding is a QR code scanned in person, so
there is no account to steal and no server to raid. That moves the attack to the
one place that holds the answer: the vouch database on each member's device.
`~/.javidnet/trust.db` records who vouched whom. A device that is seized while
unlocked hands over a slice of a real social network of people who are helping
each other reach the internet. Revocation cascades protect the network by
removing everyone a compromised member vouched for, and the same records are
what make the cascade possible.

Under those three routes, the questions worth asking about any change are: does
this make a node easier to find, does it widen what one seized device gives up,
and does it make a gateway operator more exposed than a leaf user.

## The current state of the code, stated plainly

Read this before you report. The repository is marked Blueprint, and these gaps
are known. They are documented here so that nobody spends a week rediscovering
them.

- **Mesh payloads are not encrypted by this code.** `Node._decrypt()` in
  `core/node.py` returns its input unchanged and refers to a tunnel layer that
  does not exist in this repository. The frame format defines an `encrypted`
  flag and the documentation lists TLS 1.3 at layer 4. Neither is implemented
  here yet.
- **The gateway accepts every tunnel session.** `gateway/satellite.py` reads a
  peer's identity in the handshake and then accepts it. Checking that peer
  against the trust database is a comment, not code.
- **No mesh transport exists.** The `mesh/` package is empty. Wi-Fi, BLE, and
  LoRa transports are described and are not written.
- **The emergency wipe unlinks files.** `ResilienceManager` removes the
  `~/.javidnet` directory. On flash storage, removing a file usually does not
  make its contents unrecoverable.

Those four are gaps in an unfinished implementation, not vulnerabilities. Do not
report them. Designs and pull requests that close them are the most useful thing
anyone can contribute.

## What counts as a vulnerability

- **A flaw in the design that survives a correct implementation.** This is a
  blueprint, so this is the most valuable report there is. If the architecture
  fails even when every module is written properly, say so.
- Anything that makes a node identifiable, locatable, or distinguishable from
  ordinary local traffic. Beacon contents, beacon timing, frame magic bytes,
  fixed ports, or a pattern in the routing behaviour.
- Anything that lets a member learn more of the trust graph than their own
  position in it, whether by joining, by relaying, or by asking.
- A path by which one compromised member exposes members they never vouched for.
- Anything that lets a leaf user work out where a gateway is, beyond what they
  need to route to it.
- Data that survives the emergency wipe and identifies a person or a peer.
- A statement in any README that the code or the design does not support. That
  is a security problem in this repository, not a documentation problem, because
  a reader who believes a layer is protected stops protecting it themselves. The
  four gaps listed above are exactly the class of thing that must never be
  described as working.
- Anything in the HF radio material that puts a transmitting operator at more
  risk than the material admits.

## What does not count

- **The four known gaps above.** Say the design instead of the gap.
- **Direction finding of an HF transmitter.** That is physics, not a bug. The HF
  material already covers hidden antennas and magnetic loops for this reason.
  Transmitting is the exposure. Receiving is not.
- **HF messages not being confidential.** A shortwave transmission is receivable
  by anyone in range, and a Winlink message passes through gateways and servers
  that are not yours. HF is a channel for getting a message out of a blackout,
  not a private channel. Protect the content before it reaches the radio.
- **Owning the hardware being the real risk.** True, and outside the reach of
  any code here. The README disclaimer covers it.
- **A member being able to flood the mesh.** At this stage any vouched member
  can degrade the network. Rate limiting and fair queueing are unwritten. A
  design for them is welcome as a pull request rather than as a report.
- **The capacity estimates being optimistic.** They are estimates, and the
  README says the real numbers depend on usage and cache hit rates. A
  measurement that contradicts them is a very welcome issue, and it is not a
  security report.
- **Bugs in Starlink, Winlink, llama.cpp, or the `cryptography` package.**
  Report those upstream.

## What to put in a report

The module or the diagram, what an attacker gains, and the steps that show it.

Do not include your location, your operator, your callsign, your grid square, or
a capture from a live network. See CODE_OF_CONDUCT.md. If a redacted description
does not carry the point, say so and we will find another way.

## What you get back

One maintainer works on this, so these are targets and not guarantees:

- An acknowledgement within 7 days.
- An assessment within 14 days: accepted, not accepted, or still open, with the
  reason.
- A fix or a design change, or a written statement of why there will not be one.

If 14 days pass with no reply, send it again. Silence is a missed message, not a
decision.

There is no bounty. This project has no money in it.

Credit is yours if you ask for it, and is off by default. Do not put your name,
your country, or your callsign in a report unless you are content for it to
become public.
