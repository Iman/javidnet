"""
JavidNet — Resilience Layer

What happens when the satellite goes down?  When the dish is seized?
When all gateways in a city go offline?

JavidNet doesn't crash.  It degrades gracefully:

  Level 0: FULL        — satellite active, normal operation
  Level 1: DEGRADED    — satellite intermittent, queue + retry
  Level 2: MESH_ONLY   — no satellite, local mesh messaging still works
  Level 3: SNEAKERNET  — no mesh connectivity, store for physical transfer

This module manages the transition between levels and ensures
no message is lost during transitions.

Store-and-forward:
  When the satellite is down, outbound requests are queued to disk.
  When connectivity returns, the queue drains automatically.
  For urgent messages, users can physically carry a USB stick
  to a working gateway (sneakernet).

Dead drops:
  In MESH_ONLY mode, users can still communicate locally.
  Messages addressed to the mesh stay on the mesh.
  Messages addressed to the internet are queued for later delivery.
"""
import os
import json
import time
import asyncio
import hashlib
import logging
import sqlite3
from enum import IntEnum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Awaitable

logger = logging.getLogger("javidnet.resilience")

JAVIDNET_DIR = Path.home() / ".javidnet"
QUEUE_DIR = JAVIDNET_DIR / "queue"
QUEUE_DB = JAVIDNET_DIR / "queue.db"


class DegradationLevel(IntEnum):
    FULL = 0
    DEGRADED = 1
    MESH_ONLY = 2
    SNEAKERNET = 3


@dataclass
class QueuedMessage:
    """A message waiting for satellite connectivity."""
    msg_id: str
    destination: str          # hostname:port or mesh node_id
    payload: bytes
    priority: int = 3         # 1=critical, 5=background
    created: float = 0.0
    attempts: int = 0
    last_attempt: float = 0.0
    max_attempts: int = 50
    ttl_hours: int = 72       # expire after 3 days


class ResilienceManager:
    """
    Manages network degradation and message queuing.

        rm = ResilienceManager()
        await rm.start()
        rm.set_level(DegradationLevel.DEGRADED)
        await rm.queue_message(msg)
    """

    def __init__(self):
        self.level = DegradationLevel.FULL
        self._db: Optional[sqlite3.Connection] = None
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._send_fn: Optional[Callable] = None  # callback to send via gateway
        self._listeners: List[Callable] = []

    async def start(self, send_fn: Optional[Callable] = None):
        self._send_fn = send_fn
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._running = True
        self._tasks.append(asyncio.create_task(self._drain_loop()))
        self._tasks.append(asyncio.create_task(self._expire_loop()))
        pending = self._pending_count()
        logger.info(f"Resilience manager started — level={self.level.name}, "
                    f"queued={pending}")

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._db:
            self._db.close()

    def _init_db(self):
        self._db = sqlite3.connect(str(QUEUE_DB))
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                msg_id      TEXT PRIMARY KEY,
                destination TEXT NOT NULL,
                payload     BLOB NOT NULL,
                priority    INTEGER DEFAULT 3,
                created     REAL NOT NULL,
                attempts    INTEGER DEFAULT 0,
                last_attempt REAL DEFAULT 0,
                max_attempts INTEGER DEFAULT 50,
                ttl_hours   INTEGER DEFAULT 72,
                delivered   INTEGER DEFAULT 0
            )
        """)
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority, created)")
        self._db.commit()

    # ── Level management ──────────────────────────────────

    def set_level(self, level: DegradationLevel):
        old = self.level
        self.level = level
        if old != level:
            logger.warning(f"Degradation level: {old.name} → {level.name}")
            for listener in self._listeners:
                try:
                    listener(old, level)
                except Exception:
                    pass

    def on_level_change(self, callback: Callable):
        self._listeners.append(callback)

    # ── Message queuing ───────────────────────────────────

    async def queue_message(self, msg: QueuedMessage):
        """
        Add a message to the persistent queue.
        Messages survive restarts, power cuts, and crash loops.
        """
        if not msg.msg_id:
            msg.msg_id = hashlib.sha256(
                f"{msg.destination}:{time.time()}:{os.urandom(8).hex()}".encode()
            ).hexdigest()[:16]
        if msg.created == 0:
            msg.created = time.time()

        self._db.execute("""
            INSERT OR REPLACE INTO queue
            (msg_id, destination, payload, priority, created, attempts, max_attempts, ttl_hours)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        """, (msg.msg_id, msg.destination, msg.payload, msg.priority,
              msg.created, msg.max_attempts, msg.ttl_hours))
        self._db.commit()

        logger.debug(f"Queued message {msg.msg_id} → {msg.destination} "
                     f"(priority={msg.priority})")

    async def _drain_loop(self):
        """
        Continuously try to deliver queued messages when satellite is up.
        """
        while self._running:
            if self.level <= DegradationLevel.DEGRADED and self._send_fn:
                await self._drain_batch()
            await asyncio.sleep(5 if self.level == DegradationLevel.FULL else 30)

    async def _drain_batch(self, batch_size: int = 10):
        """Try to deliver the highest-priority queued messages."""
        rows = self._db.execute("""
            SELECT msg_id, destination, payload, priority, attempts
            FROM queue
            WHERE delivered = 0 AND attempts < max_attempts
            ORDER BY priority ASC, created ASC
            LIMIT ?
        """, (batch_size,)).fetchall()

        for row in rows:
            msg_id, dest, payload, priority, attempts = row
            try:
                success = await self._send_fn(dest, payload)
                if success:
                    self._db.execute(
                        "UPDATE queue SET delivered=1 WHERE msg_id=?", (msg_id,)
                    )
                    logger.debug(f"Delivered queued message {msg_id}")
                else:
                    self._db.execute(
                        "UPDATE queue SET attempts=attempts+1, last_attempt=? WHERE msg_id=?",
                        (time.time(), msg_id)
                    )
            except Exception as e:
                self._db.execute(
                    "UPDATE queue SET attempts=attempts+1, last_attempt=? WHERE msg_id=?",
                    (time.time(), msg_id)
                )
                logger.debug(f"Delivery failed for {msg_id}: {e}")

        self._db.commit()

    async def _expire_loop(self):
        """Remove messages that exceeded their TTL."""
        while self._running:
            now = time.time()
            self._db.execute("""
                DELETE FROM queue
                WHERE delivered = 1
                   OR (created + ttl_hours * 3600) < ?
                   OR attempts >= max_attempts
            """, (now,))
            self._db.commit()
            await asyncio.sleep(300)  # every 5 minutes

    def _pending_count(self) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM queue WHERE delivered=0"
        ).fetchone()
        return row[0] if row else 0

    # ── Sneakernet (USB dead drop) ────────────────────────

    async def export_to_usb(self, path: str) -> int:
        """
        Export pending messages to a USB stick for physical transport.

        Use case: all gateways in your city are down, but you know
        someone traveling to another city where gateways work.
        Give them a USB stick with your queued messages.
        """
        export_dir = Path(path) / "javidnet_export"
        export_dir.mkdir(parents=True, exist_ok=True)

        rows = self._db.execute("""
            SELECT msg_id, destination, payload, priority, created
            FROM queue WHERE delivered = 0
            ORDER BY priority ASC, created ASC
        """).fetchall()

        manifest = []
        for row in rows:
            msg_id, dest, payload, priority, created = row
            msg_file = export_dir / f"{msg_id}.jnm"
            msg_data = {
                "id": msg_id,
                "dest": dest,
                "priority": priority,
                "created": created,
            }
            # Write header + payload
            header = json.dumps(msg_data).encode()
            msg_file.write_bytes(
                len(header).to_bytes(4, "big") + header + payload
            )
            manifest.append(msg_data)

        # Write manifest
        (export_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )
        logger.info(f"Exported {len(manifest)} messages to {export_dir}")
        return len(manifest)

    async def import_from_usb(self, path: str) -> int:
        """
        Import messages from a USB stick and deliver them.
        Called at a gateway that has satellite connectivity.
        """
        export_dir = Path(path) / "javidnet_export"
        if not export_dir.exists():
            return 0

        count = 0
        for msg_file in export_dir.glob("*.jnm"):
            data = msg_file.read_bytes()
            header_len = int.from_bytes(data[:4], "big")
            header = json.loads(data[4:4 + header_len])
            payload = data[4 + header_len:]

            msg = QueuedMessage(
                msg_id=header["id"],
                destination=header["dest"],
                payload=payload,
                priority=header.get("priority", 3),
                created=header.get("created", time.time()),
            )
            await self.queue_message(msg)
            count += 1

        logger.info(f"Imported {count} messages from {export_dir}")
        return count

    # ── Emergency wipe ────────────────────────────────────

    async def emergency_wipe(self):
        """
        Destroy all data.  Called when physical compromise is suspected.

        Wipes: keys, peer database, trust chain, message queue, cache.
        """
        import shutil

        logger.critical("EMERGENCY WIPE initiated")

        # Close database connections
        if self._db:
            self._db.close()
            self._db = None

        # Remove all JavidNet data
        if JAVIDNET_DIR.exists():
            shutil.rmtree(JAVIDNET_DIR)

        logger.critical("All JavidNet data destroyed")

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> Dict:
        pending = self._pending_count()
        delivered = self._db.execute(
            "SELECT COUNT(*) FROM queue WHERE delivered=1"
        ).fetchone()[0] if self._db else 0

        return {
            "degradation_level": self.level.name,
            "pending_messages": pending,
            "delivered_messages": delivered,
        }
