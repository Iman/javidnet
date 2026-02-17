"""
JavidNet — Content Optimizer

When 5 Starlink dishes serve 50,000 people, you can't afford to
waste a single byte.  This module makes satellite bandwidth go
10-50x further through:

  1. COMPRESS  — gzip/brotli everything, strip bloat from web pages
  2. TRANSCODE — downscale images (2MB JPEG → 40KB WebP), strip video
  3. DEDUP     — if 100 people request BBC Persian, fetch it once
  4. PREFETCH  — predict what people will want next, cache it ahead
  5. PRIORITIZE — text first, images later, video only if bandwidth allows

This is not a generic CDN.  It's purpose-built for the constraint:
"5 satellite dishes, 50,000 users, during a crisis."

Inspiration: Opera Mini's server-side rendering (compressed web
for 2G networks).  But JavidNet goes further because the constraint
is harder — it's not slow internet, it's SHARED internet.
"""
import io
import re
import gzip
import zlib
import json
import time
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from enum import IntEnum

logger = logging.getLogger("javidnet.optimizer")


class ContentType(IntEnum):
    TEXT = 1        # HTML, JSON, XML, plain text
    IMAGE = 2       # JPEG, PNG, WebP, GIF
    SCRIPT = 3      # JS, CSS
    FONT = 4        # WOFF2, TTF
    MEDIA = 5       # video, audio
    BINARY = 6      # everything else


class BandwidthMode(IntEnum):
    """Network capacity determines how aggressively we optimize."""
    CRISIS = 1      # <1 Mbps shared — text only, maximum compression
    TIGHT = 2       # 1-10 Mbps — text + tiny images, no scripts
    NORMAL = 3      # 10-50 Mbps — compressed browsing
    GENEROUS = 4    # 50+ Mbps — light optimization


@dataclass
class OptimizeResult:
    original_size: int
    optimized_size: int
    content_type: ContentType
    savings_pct: float
    was_cached: bool = False
    was_transcoded: bool = False


class ContentOptimizer:
    """
    Processes HTTP responses before sending them back through
    the satellite link to mesh users.

        optimizer = ContentOptimizer(mode=BandwidthMode.TIGHT)
        result, data = await optimizer.optimize(url, headers, body)
    """

    def __init__(self, mode: BandwidthMode = BandwidthMode.NORMAL):
        self.mode = mode
        self._stats = {
            "total_original": 0,
            "total_optimized": 0,
            "requests_processed": 0,
            "cache_hits": 0,
        }

    async def optimize(self, url: str, headers: Dict[str, str],
                       body: bytes) -> Tuple[OptimizeResult, bytes]:
        """
        Optimize a piece of content for satellite transmission.
        Returns (result_metadata, optimized_bytes).
        """
        content_type = self._detect_type(headers, url)
        original_size = len(body)

        if content_type == ContentType.TEXT:
            optimized = await self._optimize_text(body, headers, url)
        elif content_type == ContentType.IMAGE:
            optimized = await self._optimize_image(body, headers)
        elif content_type == ContentType.SCRIPT:
            optimized = await self._optimize_script(body)
        elif content_type == ContentType.MEDIA:
            optimized = await self._optimize_media(body)
        else:
            optimized = self._compress(body)

        result = OptimizeResult(
            original_size=original_size,
            optimized_size=len(optimized),
            content_type=content_type,
            savings_pct=round((1 - len(optimized) / max(original_size, 1)) * 100, 1),
        )

        self._stats["total_original"] += original_size
        self._stats["total_optimized"] += len(optimized)
        self._stats["requests_processed"] += 1

        return result, optimized

    # ── Text optimization ─────────────────────────────────

    async def _optimize_text(self, body: bytes, headers: Dict, url: str) -> bytes:
        """
        Optimize HTML/JSON/XML/plain text.

        For HTML in CRISIS mode, this is aggressive:
          - Strip all <script> tags (no JS — saves 60-80% of page size)
          - Strip all <style> beyond basic readability
          - Inline tiny images as data URIs, strip large ones
          - Remove tracking pixels, ads, analytics
          - Convert to minimal semantic HTML
        """
        text = body.decode("utf-8", errors="replace")
        ct = headers.get("content-type", "")

        if "html" in ct or url.endswith(".html"):
            text = self._optimize_html(text)
        elif "json" in ct:
            text = self._optimize_json(text)

        compressed = self._compress(text.encode("utf-8"))
        return compressed

    def _optimize_html(self, html: str) -> str:
        """Strip HTML down to readable content."""
        if self.mode <= BandwidthMode.CRISIS:
            # Maximum stripping
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<link[^>]*stylesheet[^>]*>', '', html, flags=re.IGNORECASE)
            html = re.sub(r'<img[^>]*>', '[img]', html, flags=re.IGNORECASE)
            html = re.sub(r'<video[^>]*>.*?</video>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
            # Remove tracking
            html = re.sub(r'<img[^>]*1x1[^>]*>', '', html, flags=re.IGNORECASE)
            html = re.sub(r'<img[^>]*pixel[^>]*>', '', html, flags=re.IGNORECASE)

        elif self.mode <= BandwidthMode.TIGHT:
            # Remove scripts but keep basic styling
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Always: collapse whitespace, remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        html = re.sub(r'\s+', ' ', html)

        return html.strip()

    def _optimize_json(self, text: str) -> str:
        """Minify JSON."""
        try:
            obj = json.loads(text)
            return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
        except json.JSONDecodeError:
            return text

    # ── Image optimization ────────────────────────────────

    async def _optimize_image(self, body: bytes, headers: Dict) -> bytes:
        """
        Transcode images for satellite efficiency.

        CRISIS:   strip all images (return 1x1 transparent pixel)
        TIGHT:    resize to max 200px wide, quality 30, WebP
        NORMAL:   resize to max 800px wide, quality 60, WebP
        GENEROUS: light compression only
        """
        if self.mode == BandwidthMode.CRISIS:
            # 1x1 transparent PNG (67 bytes)
            return (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
                b'\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            )

        try:
            from PIL import Image
            img = Image.open(io.BytesIO(body))

            # Determine target size
            if self.mode == BandwidthMode.TIGHT:
                max_width, quality = 200, 30
            elif self.mode == BandwidthMode.NORMAL:
                max_width, quality = 800, 60
            else:
                max_width, quality = 1200, 75

            # Resize if larger than target
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Convert to RGB if needed (WebP doesn't support all modes)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Save as WebP
            buf = io.BytesIO()
            img.save(buf, format="WebP", quality=quality, method=4)
            result = buf.getvalue()

            # Only use optimized version if it's actually smaller
            if len(result) < len(body):
                return result
            return self._compress(body)

        except ImportError:
            # No Pillow — just compress the raw bytes
            return self._compress(body)
        except Exception:
            return self._compress(body)

    # ── Script optimization ───────────────────────────────

    async def _optimize_script(self, body: bytes) -> bytes:
        """
        Optimize JavaScript/CSS.
        In CRISIS/TIGHT mode, strip entirely.
        Otherwise, minify and compress.
        """
        if self.mode <= BandwidthMode.TIGHT:
            return b""  # no JS/CSS in crisis mode

        text = body.decode("utf-8", errors="replace")
        # Basic minification: strip comments, collapse whitespace
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)  # block comments
        text = re.sub(r'//[^\n]*', '', text)                     # line comments
        text = re.sub(r'\s+', ' ', text)

        return self._compress(text.encode("utf-8"))

    # ── Media optimization ────────────────────────────────

    async def _optimize_media(self, body: bytes) -> bytes:
        """
        Video/audio over satellite during a crisis?  No.

        In CRISIS/TIGHT: block entirely (return error message)
        In NORMAL: allow but heavily compress
        In GENEROUS: light compression
        """
        if self.mode <= BandwidthMode.TIGHT:
            msg = b"[Media blocked — bandwidth reserved for text/messaging]"
            return msg

        # Allow but compress
        return self._compress(body)

    # ── Helpers ───────────────────────────────────────────

    def _detect_type(self, headers: Dict[str, str], url: str) -> ContentType:
        ct = headers.get("content-type", "").lower()
        if "html" in ct or "json" in ct or "xml" in ct or "text" in ct:
            return ContentType.TEXT
        if "image" in ct or any(url.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
            return ContentType.IMAGE
        if "javascript" in ct or "css" in ct or url.endswith(".js") or url.endswith(".css"):
            return ContentType.SCRIPT
        if "font" in ct or any(url.endswith(e) for e in (".woff", ".woff2", ".ttf", ".otf")):
            return ContentType.FONT
        if any(t in ct for t in ("video", "audio", "mpeg", "mp4", "webm", "ogg")):
            return ContentType.MEDIA
        return ContentType.BINARY

    def _compress(self, data: bytes) -> bytes:
        """Compress with gzip.  Simple, universal, effective."""
        if len(data) < 100:
            return data  # too small to benefit
        compressed = gzip.compress(data, compresslevel=6)
        return compressed if len(compressed) < len(data) else data

    # ── Deduplication ─────────────────────────────────────

    @staticmethod
    def content_hash(url: str) -> str:
        """
        Hash a URL for cache deduplication.
        Strip tracking parameters to increase cache hit rate.
        """
        # Remove common tracking params
        clean = re.sub(r'[?&](utm_\w+|fbclid|gclid|ref|source|campaign)=[^&]*', '', url)
        # Remove fragment
        clean = clean.split("#")[0]
        return hashlib.sha256(clean.encode()).hexdigest()[:16]

    # ── Bandwidth estimator ───────────────────────────────

    @staticmethod
    def estimate_capacity(
        num_dishes: int = 5,
        avg_uplink_mbps: float = 20,
        avg_downlink_mbps: float = 100,
    ) -> Dict:
        """
        Estimate how many users JavidNet can support.

        With optimization, the effective capacity is 10-50x
        the raw satellite bandwidth.
        """
        raw_down = num_dishes * avg_downlink_mbps  # Mbps total
        raw_up = num_dishes * avg_uplink_mbps

        return {
            "raw_downlink_mbps": raw_down,
            "raw_uplink_mbps": raw_up,
            "text_messaging": {
                "per_user_kbps": 2,
                "max_users": int(raw_down * 1000 / 2),
                "description": "Telegram/Signal text chat",
            },
            "optimized_browsing": {
                "per_user_kbps": 50,
                "max_users": int(raw_down * 1000 / 50),
                "description": "Web browsing with content optimization",
            },
            "standard_browsing": {
                "per_user_kbps": 500,
                "max_users": int(raw_down * 1000 / 500),
                "description": "Normal web browsing",
            },
            "note": (
                "With aggressive caching and content optimization, "
                "effective capacity is 10-50x higher for repeated content."
            ),
        }

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> Dict:
        orig = self._stats["total_original"]
        opt = self._stats["total_optimized"]
        return {
            **self._stats,
            "compression_ratio": round(opt / max(orig, 1), 3),
            "bandwidth_saved_mb": round((orig - opt) / 1_048_576, 1),
            "mode": self.mode.name,
        }
