# Contributing

Thank you for looking at this. Read SECURITY.md before you open anything public,
and read CODE_OF_CONDUCT.md before you ask anyone a question about their setup or
their location.

The README lists the kinds of help this project wants. This file covers how to
work on the repository itself.

## What this repository is

Three things in one place, and they are worked on differently.

| Part | What it is | How to change it |
|------|-----------|------------------|
| `starlink-meshnetwork/` | Python implementation of the mesh | Code |
| `hf-radio-diagrams/` | HF radio reference and diagrams | Documentation and drawio |
| Root READMEs and `png/` | Architecture and design | Documentation and drawio |

The badge says Blueprint and it means it. Large parts of the design are written
down and not built. SECURITY.md lists four gaps between the documents and the
code. Read that list before you start, so you do not spend a week finding them
again.

## Running the code

Python 3.10 or newer. One required dependency.

```bash
cd starlink-meshnetwork
pip install -r requirements.txt
```

Only `cryptography` is required. `Pillow` is optional and is used for image
transcoding.

Run from inside `starlink-meshnetwork/`. The modules import each other by
top-level package name, as in `from core.node import Node`, so running from the
repository root fails with an import error.

```bash
python3 javidnet.py leaf --socks-port 1080
python3 javidnet.py hop
python3 javidnet.py gateway --cache-size 2000 --max-sessions 200
```

## There is no test suite and no CI

Say that plainly rather than work around it: this repository has no unit tests,
no integration tests, and no GitHub Actions workflow. A pull request is reviewed
by reading it and by running it.

Here is what you can run instead.

### Parse every module

```bash
cd starlink-meshnetwork
python3 -m compileall -q .
```

This is worth more than it looks. Run today, it reports a real syntax error in
`optimizer/content.py`, on a line that nothing imports, so the module has never
been loaded by the CLI. Run this before you push.

### Run two nodes on one machine

Peers find each other with UDP multicast to `239.77.43.1` on the mesh port, so
both nodes must use the **same** `--port`. The listener sets `SO_REUSEADDR`, so
two processes on one host can share it. Only the SOCKS port differs.

```bash
python3 javidnet.py hop --port 7743
python3 javidnet.py leaf --port 7743 --socks-port 1080
```

If your operating system refuses the second bind, run the second node on another
machine on the same network segment.

Then send traffic through the proxy:

```bash
curl --proxy socks5h://127.0.0.1:1080 https://example.com
```

Do not test on a live mesh, and do not ask anybody else to. See
CODE_OF_CONDUCT.md.

### Say what you ran

In the pull request, write what you ran and what you did not. "Parsed and ran
two nodes locally, no gateway hardware" is a useful sentence. A claim of testing
that did not happen is worse than no test at all.

## Writing code for a blueprint project

The most important rule in this repository follows from its state.

**Do not describe unwritten code as working.** When you add a module, say in the
same pull request which parts of it are real and which are placeholders. When
you find documentation that describes something the code does not do, correct
the documentation, and do not soften it. A reader who believes a layer is
encrypted stops encrypting. That is the failure mode this project cannot afford,
and it is why SECURITY.md treats a wrong sentence as a security bug.

Other rules:

- Keep the standard library and `cryptography` as the only requirements for the
  core path. This code has to run on a Raspberry Pi over a satellite link with
  no package mirror. Every new dependency is a download somebody may not be able
  to make.
- Anything new that a node puts on the air becomes a fingerprint. A new frame
  type, a new interval, a new port, or a new constant is a way to recognise a
  JavidNet node. Say in the pull request what your change adds to what an
  observer can see.
- Never write a real address, key, callsign, or node id into the repository, in
  code or in a test fixture.

## Diagrams

Diagrams are drawio sources with exported PNGs beside them, in English and in
Persian. Change the `.drawio` source and re-export. Do not hand-edit a PNG.

```bash
bash scripts/drawio-to-png.sh path/to/diagram.drawio
DRAWIO_VERIFY_ONLY=1 bash scripts/drawio-to-png.sh
```

The script prefers the native draw.io CLI, then `npx @drawio/cli`, then Docker.
`DRAWIO_VERIFY_ONLY=1` checks that every PNG exists and is valid without
exporting anything.

Commit both the source and the exported PNG in the same pull request.

## Documentation is bilingual

Every document has a Persian counterpart:

- `README.md` and `README.fa.md`
- `STARLINK_MESHNETWORK_README.md` and `STARLINK_MESHNETWORK_README.fa.md`
- `starlink-meshnetwork/README.md` and `README.fa.md`
- `hf-radio-diagrams/README.md` and `README.fa.md`, with Persian diagram sources
  under `hf-radio-diagrams/farsi/`

Change both in the same pull request, or say in the description that the Persian
version still needs doing so it is not forgotten. A correction that lands in one
language and not the other leaves the wrong sentence standing for the readers
who most need it.

No emoji, no ANSI escape codes, and no em dashes anywhere: not in documentation,
not in code, not in comments, not in commit messages, not in branch names. The
syntax error mentioned above is an em dash inside a bytes literal, which is
exactly how that rule stops being a matter of taste.

## Things worth doing that are not new features

- Reading the architecture and finding a flaw in it. This is a design document
  more than a product, so a flaw in the design is the most valuable thing anyone
  can contribute.
- Closing one of the four gaps listed in SECURITY.md, starting with the tunnel
  encryption layer.
- Measuring a capacity claim and reporting what you actually got.
- Persian translation, and correcting the Persian that is already there.
