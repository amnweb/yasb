from __future__ import annotations

import json
import sqlite3
import time
import zlib
from pathlib import Path

from core.utils.system import app_data_path

from .models import Hit, Query

DEFAULT_DB_PATH = app_data_path("lyrics") / "lyrics.db"

# Expired rows are swept at startup, but only once the table is large enough to be
# worth a full scan; below this the per-key deletes in get() keep it bounded.
SWEEP_MIN_ROWS = 256


class LyricsCache:
    """SQLite cache for lyric results and misses."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
                conn.execute("PRAGMA auto_vacuum = INCREMENTAL")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lyrics_cache (
                    key TEXT PRIMARY KEY,
                    hits_blob BLOB NOT NULL,
                    cached_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS negative_cache (
                    key TEXT PRIMARY KEY,
                    cached_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            self._sweep_expired(conn)
            conn.commit()
            conn.execute("PRAGMA incremental_vacuum")

    def _sweep_expired(self, conn: sqlite3.Connection) -> None:
        now = time.time()
        count_row = conn.execute("SELECT COUNT(*) FROM lyrics_cache").fetchone()
        if count_row and int(count_row[0]) >= SWEEP_MIN_ROWS:
            conn.execute("DELETE FROM lyrics_cache WHERE expires_at <= ?", (now,))
        conn.execute("DELETE FROM negative_cache WHERE expires_at <= ?", (now,))

    def get(self, query: Query) -> list[Hit] | None:
        key = query.clean_key()
        now = time.time()

        with self._get_connection() as conn:
            neg_row = conn.execute("SELECT expires_at FROM negative_cache WHERE key = ?", (key,)).fetchone()
            if neg_row:
                if neg_row["expires_at"] > now:
                    return []
                else:
                    conn.execute("DELETE FROM negative_cache WHERE key = ?", (key,))
                    conn.commit()

            row = conn.execute("SELECT hits_blob, expires_at FROM lyrics_cache WHERE key = ?", (key,)).fetchone()
            if row:
                if row["expires_at"] > now:
                    try:
                        raw_list = json.loads(zlib.decompress(row["hits_blob"]).decode("utf-8"))
                        return [Hit.from_dict(item) for item in raw_list]
                    except Exception:
                        pass
                else:
                    conn.execute("DELETE FROM lyrics_cache WHERE key = ?", (key,))
                    conn.commit()

        return None

    def set(self, query: Query, hits: list[Hit], ttl_seconds: int = 7 * 86400) -> None:
        """Stores hits for a query with an expiration TTL (default 7 days)."""
        key = query.clean_key()
        now = time.time()
        expires = now + ttl_seconds
        payload = zlib.compress(json.dumps([h.to_dict() for h in hits], ensure_ascii=False).encode("utf-8"))

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO lyrics_cache (key, hits_blob, cached_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, payload, now, expires),
            )
            conn.execute("DELETE FROM negative_cache WHERE key = ?", (key,))
            conn.commit()

    def set_negative(self, query: Query, ttl_seconds: int = 86400) -> None:
        """Stores a negative hit (no lyrics found) with a 24-hour TTL."""
        key = query.clean_key()
        now = time.time()
        expires = now + ttl_seconds

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO negative_cache (key, cached_at, expires_at)
                VALUES (?, ?, ?)
                """,
                (key, now, expires),
            )
            conn.commit()

    put = set
    put_instrumental = set_negative

    def clear(self) -> None:
        """Purges all cached hits and negative lookups."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM lyrics_cache")
            conn.execute("DELETE FROM negative_cache")
            conn.commit()
