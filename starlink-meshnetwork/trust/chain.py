"""
JavidNet — Trust Chain

How do you build a trusted network with no central authority,
no certificate authority, no directory server, and no internet?

Answer: a web of trust with physical verification.

The trust model:

  Level 3: OPERATOR  — runs a gateway dish.  Self-declared.
  Level 2: TRUSTED   — vouched by an operator.  Can vouch others.
  Level 1: VOUCHED   — vouched by a trusted peer.  Can use the network.
  Level 0: UNKNOWN   — can see beacons but can't route traffic.

Onboarding flow:
  1. New user installs JavidNet → generates keypair → trust=0
  2. Meets an existing member in person
  3. Existing member scans new user's QR code (contains public key)
  4. Existing member signs a vouch: "I vouch for <pubkey>"
  5. New user is now trust=1, can use the network

This is intentionally slow.  Speed = infiltration risk.
Every vouch is a personal guarantee.  If you vouch for an agent,
your own trust is revoked.

The QR code is the handshake.  No SMS, no email, no app store.
Two phones, one camera, one screen.  That's it.
"""
import os
import json
import time
import hashlib
import logging
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from enum import IntEnum

logger = logging.getLogger("javidnet.trust")

JAVIDNET_DIR = Path.home() / ".javidnet"
TRUST_DB_PATH = JAVIDNET_DIR / "trust.db"


class TrustLevel(IntEnum):
    UNKNOWN = 0
    VOUCHED = 1
    TRUSTED = 2
    OPERATOR = 3


@dataclass
class Vouch:
    """A signed statement: 'I vouch for this peer.'"""
    voucher_id: str          # node_id of the voucher
    voucher_pubkey: bytes    # public key of the voucher
    target_id: str           # node_id being vouched for
    target_pubkey: bytes     # public key of the target
    granted_level: int       # trust level granted
    timestamp: int           # unix time
    signature: bytes         # Ed25519 signature of the above
    note: str = ""           # optional human-readable note


class TrustDB:
    """
    Local trust database.  Stores vouches and computes trust levels.

    Uses SQLite — a single file, no server, works offline.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(TRUST_DB_PATH)
        self._conn: Optional[sqlite3.Connection] = None

    def open(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def close(self):
        if self._conn:
            self._conn.close()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS peers (
                node_id     TEXT PRIMARY KEY,
                public_key  BLOB NOT NULL,
                trust_level INTEGER DEFAULT 0,
                vouched_by  TEXT,
                first_seen  INTEGER,
                last_seen   INTEGER,
                revoked     INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS vouches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_id  TEXT NOT NULL,
                target_id   TEXT NOT NULL,
                level       INTEGER NOT NULL,
                timestamp   INTEGER NOT NULL,
                signature   BLOB NOT NULL,
                note        TEXT DEFAULT '',
                UNIQUE(voucher_id, target_id)
            );
            CREATE TABLE IF NOT EXISTS revocations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                revoker_id  TEXT NOT NULL,
                target_id   TEXT NOT NULL,
                reason      TEXT,
                timestamp   INTEGER NOT NULL,
                signature   BLOB NOT NULL
            );
        """)

    # ── Peer management ───────────────────────────────────

    def add_peer(self, node_id: str, public_key: bytes, trust_level: int = 0):
        now = int(time.time())
        self._conn.execute("""
            INSERT INTO peers (node_id, public_key, trust_level, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET last_seen=?, trust_level=MAX(trust_level, ?)
        """, (node_id, public_key, trust_level, now, now, now, trust_level))
        self._conn.commit()

    def get_trust(self, node_id: str) -> int:
        row = self._conn.execute(
            "SELECT trust_level, revoked FROM peers WHERE node_id=?", (node_id,)
        ).fetchone()
        if not row:
            return TrustLevel.UNKNOWN
        if row[1]:  # revoked
            return TrustLevel.UNKNOWN
        return row[0]

    def get_peer(self, node_id: str) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT node_id, public_key, trust_level, vouched_by, first_seen, revoked "
            "FROM peers WHERE node_id=?", (node_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "node_id": row[0], "public_key": row[1], "trust_level": row[2],
            "vouched_by": row[3], "first_seen": row[4], "revoked": bool(row[5]),
        }

    def list_trusted(self, min_level: int = 1) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT node_id, trust_level, vouched_by FROM peers "
            "WHERE trust_level >= ? AND revoked = 0 ORDER BY trust_level DESC",
            (min_level,)
        ).fetchall()
        return [{"node_id": r[0], "trust_level": r[1], "vouched_by": r[2]} for r in rows]

    # ── Vouching ──────────────────────────────────────────

    def record_vouch(self, vouch: Vouch) -> bool:
        """
        Record a vouch and update the target's trust level.

        Rules:
          • OPERATOR (3) can vouch someone up to TRUSTED (2)
          • TRUSTED (2) can vouch someone up to VOUCHED (1)
          • VOUCHED (1) cannot vouch anyone
          • You can't vouch yourself
          • You can't vouch someone already revoked
        """
        if vouch.voucher_id == vouch.target_id:
            return False

        # Check voucher's trust level
        voucher_trust = self.get_trust(vouch.voucher_id)
        if voucher_trust < TrustLevel.TRUSTED:
            logger.warning(f"Vouch rejected: {vouch.voucher_id} trust={voucher_trust} < TRUSTED")
            return False

        # Max level the voucher can grant
        max_grantable = min(vouch.granted_level, voucher_trust - 1)
        if max_grantable < TrustLevel.VOUCHED:
            return False

        # Verify signature
        if not self._verify_vouch_signature(vouch):
            logger.warning(f"Vouch rejected: invalid signature from {vouch.voucher_id}")
            return False

        # Check if target is revoked
        target = self.get_peer(vouch.target_id)
        if target and target.get("revoked"):
            logger.warning(f"Vouch rejected: {vouch.target_id} is revoked")
            return False

        # Record vouch
        self._conn.execute("""
            INSERT OR REPLACE INTO vouches (voucher_id, target_id, level, timestamp, signature, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (vouch.voucher_id, vouch.target_id, max_grantable,
              vouch.timestamp, vouch.signature, vouch.note))

        # Update peer's trust level
        self.add_peer(vouch.target_id, vouch.target_pubkey, max_grantable)
        self._conn.execute(
            "UPDATE peers SET vouched_by=?, trust_level=? WHERE node_id=?",
            (vouch.voucher_id, max_grantable, vouch.target_id)
        )
        self._conn.commit()

        logger.info(f"Vouch recorded: {vouch.voucher_id} → {vouch.target_id} "
                    f"(level={max_grantable})")
        return True

    # ── Revocation ────────────────────────────────────────

    def revoke(self, revoker_id: str, target_id: str, reason: str,
               signature: bytes) -> bool:
        """
        Revoke a peer's trust.  Cascading: if you're revoked,
        everyone you vouched for is also revoked.
        """
        revoker_trust = self.get_trust(revoker_id)
        target_trust = self.get_trust(target_id)

        if revoker_trust <= target_trust:
            logger.warning(f"Revocation rejected: {revoker_id} can't revoke {target_id}")
            return False

        # Record revocation
        self._conn.execute("""
            INSERT INTO revocations (revoker_id, target_id, reason, timestamp, signature)
            VALUES (?, ?, ?, ?, ?)
        """, (revoker_id, target_id, reason, int(time.time()), signature))

        # Revoke the target
        self._conn.execute(
            "UPDATE peers SET revoked=1, trust_level=0 WHERE node_id=?",
            (target_id,)
        )

        # Cascade: revoke everyone vouched by the target
        dependents = self._conn.execute(
            "SELECT node_id FROM peers WHERE vouched_by=? AND revoked=0",
            (target_id,)
        ).fetchall()

        for (dep_id,) in dependents:
            self._conn.execute(
                "UPDATE peers SET revoked=1, trust_level=0 WHERE node_id=?",
                (dep_id,)
            )
            logger.info(f"Cascade revocation: {dep_id} (vouched by revoked {target_id})")

        self._conn.commit()
        logger.info(f"Revoked: {target_id} by {revoker_id} — reason: {reason}")
        return True

    # ── QR code generation/parsing ────────────────────────

    @staticmethod
    def generate_qr_payload(node_id: str, public_key: bytes) -> str:
        """
        Generate the string encoded in a QR code for onboarding.

        Format: javidnet://<node_id>/<pubkey_hex>

        Scan this with any QR reader.  The JavidNet app parses
        the javidnet:// scheme and initiates the vouch flow.
        """
        return f"javidnet://{node_id}/{public_key.hex()}"

    @staticmethod
    def parse_qr_payload(payload: str) -> Optional[Tuple[str, bytes]]:
        """Parse a JavidNet QR code → (node_id, public_key)."""
        if not payload.startswith("javidnet://"):
            return None
        parts = payload[len("javidnet://"):].split("/")
        if len(parts) != 2:
            return None
        try:
            node_id = parts[0]
            pubkey = bytes.fromhex(parts[1])
            if len(pubkey) != 32:
                return None
            return (node_id, pubkey)
        except ValueError:
            return None

    # ── Signature helpers ─────────────────────────────────

    @staticmethod
    def sign_vouch(private_key: bytes, voucher_id: str, target_id: str,
                   target_pubkey: bytes, level: int, timestamp: int) -> bytes:
        """Sign a vouch using Ed25519."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        message = f"{voucher_id}:{target_id}:{target_pubkey.hex()}:{level}:{timestamp}".encode()
        key = Ed25519PrivateKey.from_private_bytes(private_key)
        return key.sign(message)

    def _verify_vouch_signature(self, vouch: Vouch) -> bool:
        """Verify the Ed25519 signature on a vouch."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        message = (f"{vouch.voucher_id}:{vouch.target_id}:"
                   f"{vouch.target_pubkey.hex()}:{vouch.granted_level}:"
                   f"{vouch.timestamp}").encode()
        try:
            key = Ed25519PublicKey.from_public_bytes(vouch.voucher_pubkey)
            key.verify(vouch.signature, message)
            return True
        except Exception:
            return False

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> Dict:
        total = self._conn.execute("SELECT COUNT(*) FROM peers").fetchone()[0]
        trusted = self._conn.execute(
            "SELECT COUNT(*) FROM peers WHERE trust_level >= 1 AND revoked=0"
        ).fetchone()[0]
        revoked = self._conn.execute(
            "SELECT COUNT(*) FROM peers WHERE revoked=1"
        ).fetchone()[0]
        vouches = self._conn.execute("SELECT COUNT(*) FROM vouches").fetchone()[0]

        return {
            "total_peers": total,
            "trusted_peers": trusted,
            "revoked_peers": revoked,
            "total_vouches": vouches,
        }
