"""Immutable append-only forensic audit ledger.

Design constraints
------------------
* GDPR compliance: raw PII NEVER written to disk.  Only SHA-256 digests of the
  full payload and the redacted PII type names are stored.
* Append-only: each write appends one JSONL line and calls fsync to guarantee
  durability even if the process is killed immediately after.
* Concurrency-safe: a per-instance asyncio.Lock serialises all writes from the
  multiple concurrent proxy requests that share a single ledger instance.

File layout
-----------
  ledger/data/<session_id>/transactions.jsonl
  (each line is one JSON object — standard JSONL format)
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles
import structlog

log = structlog.get_logger()

# Default storage root — override with SENTINEL_LEDGER_DIR env var
DEFAULT_LEDGER_ROOT = Path(__file__).parent / "data"


@dataclass
class TransactionEntry:
    """
    One row in the forensic ledger.

    Fields deliberately exclude raw content — only digests and metadata.
    """
    session_id: str
    original_payload_digest: str    # SHA-256 of the canonical request JSON
    verdict: str                    # "allow" | "redact" | "block"
    reason: str
    findings_count: int
    pii_types_found: list[str]      # e.g. ["email", "iban"] — no actual values
    was_forwarded: bool
    model: str = "unknown"
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TransactionLog:
    """
    Write-ahead forensic ledger for a single proxy session.

    Usage
    -----
    ledger = TransactionLog(session_id="abc123")
    await ledger.record(entry)
    entries = await ledger.tail(n=50)
    """

    def __init__(
        self,
        session_id: str = "default",
        ledger_root: Optional[Path] = None,
    ) -> None:
        root = ledger_root or Path(
            os.getenv("SENTINEL_LEDGER_DIR", str(DEFAULT_LEDGER_ROOT))
        )
        self._log_dir = root / session_id
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "transactions.jsonl"
        self._lock = asyncio.Lock()
        self._session_id = session_id
        log.info("ledger.initialised", path=str(self._log_path))

    @property
    def path(self) -> Path:
        """Absolute path to the JSONL ledger file."""
        return self._log_path

    async def record(self, entry: TransactionEntry) -> None:
        """
        Append one entry to the ledger.

        The write is atomic with respect to this process: the lock ensures no
        two concurrent requests can interleave their writes.  fsync() guarantees
        the line reaches disk before we return — critical for a forensic log.
        """
        line = json.dumps(asdict(entry), ensure_ascii=False) + "\n"
        async with self._lock:
            async with aiofiles.open(self._log_path, mode="a", encoding="utf-8") as f:
                await f.write(line)
                await f.flush()
                # fsync via the underlying file descriptor
                os.fsync(f.fileno())
        log.debug(
            "ledger.written",
            transaction_id=entry.transaction_id,
            verdict=entry.verdict,
        )

    async def tail(self, n: int = 100) -> list[dict]:
        """
        Return the last *n* entries from the ledger (most recent last).

        Reads the entire file and slices — acceptable for the ledger sizes
        expected in a single proxy session.  Replace with a seekable reader
        if sessions are expected to last days.
        """
        if not self._log_path.exists():
            return []
        async with self._lock:
            async with aiofiles.open(self._log_path, encoding="utf-8") as f:
                lines = await f.readlines()
        entries = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries[-n:]

    async def stats(self) -> dict:
        """Return aggregate counters for this session's ledger."""
        entries = await self.tail(n=10_000)
        total = len(entries)
        blocked = sum(1 for e in entries if e.get("verdict") == "block")
        redacted = sum(1 for e in entries if e.get("verdict") == "redact")
        allowed = sum(1 for e in entries if e.get("verdict") == "allow")
        pii_seen: set[str] = set()
        for e in entries:
            pii_seen.update(e.get("pii_types_found", []))
        return {
            "total_transactions": total,
            "allowed": allowed,
            "redacted": redacted,
            "blocked": blocked,
            "pii_types_encountered": sorted(pii_seen),
            "ledger_path": str(self._log_path),
        }
