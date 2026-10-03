import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from skrapper.models import Listing


@dataclass(frozen=True, slots=True)
class SearchState:
    name: str
    bootstrapped: bool
    last_checked_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    last_fetched_count: int = 0
    last_sent_count: int = 0


class ListingStorage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def init(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_listings (
                    stable_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL
                )
                """
            )
            self._add_column(connection, "seen_listings", "normalized_url TEXT")
            self._add_column(connection, "seen_listings", "fingerprint TEXT")
            self._add_column(connection, "seen_listings", "price INTEGER")
            self._add_column(connection, "seen_listings", "location TEXT")
            self._add_column(connection, "seen_listings", "last_seen_at TEXT")
            self._add_column(connection, "seen_listings", "last_notified_at TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS search_state (
                    name TEXT PRIMARY KEY,
                    bootstrapped INTEGER NOT NULL DEFAULT 0,
                    last_checked_at TEXT,
                    last_success_at TEXT,
                    last_error TEXT,
                    last_fetched_count INTEGER NOT NULL DEFAULT 0,
                    last_sent_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_seen_listings_normalized_url
                ON seen_listings(normalized_url)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_seen_listings_fingerprint
                ON seen_listings(fingerprint)
                """
            )

    def get_search_state(self, name: str) -> SearchState:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name, bootstrapped, last_checked_at, last_success_at, last_error,
                       last_fetched_count, last_sent_count
                FROM search_state
                WHERE name = ?
                """,
                (name,),
            ).fetchone()
        if row is None:
            return SearchState(name=name, bootstrapped=False)
        return SearchState(
            name=row[0],
            bootstrapped=bool(row[1]),
            last_checked_at=row[2],
            last_success_at=row[3],
            last_error=row[4],
            last_fetched_count=row[5],
            last_sent_count=row[6],
        )

    def list_search_states(self) -> list[SearchState]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, bootstrapped, last_checked_at, last_success_at, last_error,
                       last_fetched_count, last_sent_count
                FROM search_state
                ORDER BY name
                """
            ).fetchall()
        return [
            SearchState(
                name=row[0],
                bootstrapped=bool(row[1]),
                last_checked_at=row[2],
                last_success_at=row[3],
                last_error=row[4],
                last_fetched_count=row[5],
                last_sent_count=row[6],
            )
            for row in rows
        ]

    def update_search_state(
        self,
        name: str,
        *,
        bootstrapped: bool | None = None,
        fetched_count: int | None = None,
        sent_count: int | None = None,
        error: str | None = None,
        success: bool = False,
    ) -> None:
        now = utc_now()
        state = self.get_search_state(name)
        next_bootstrapped = state.bootstrapped if bootstrapped is None else bootstrapped
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO search_state (
                    name, bootstrapped, last_checked_at, last_success_at, last_error,
                    last_fetched_count, last_sent_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    bootstrapped = excluded.bootstrapped,
                    last_checked_at = excluded.last_checked_at,
                    last_success_at = excluded.last_success_at,
                    last_error = excluded.last_error,
                    last_fetched_count = excluded.last_fetched_count,
                    last_sent_count = excluded.last_sent_count
                """,
                (
                    name,
                    int(next_bootstrapped),
                    now,
                    now if success else state.last_success_at,
                    error,
                    fetched_count if fetched_count is not None else state.last_fetched_count,
                    sent_count if sent_count is not None else state.last_sent_count,
                ),
            )

    def was_observed(self, listing: Listing) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM seen_listings
                WHERE stable_key = ? OR normalized_url = ? OR fingerprint = ?
                LIMIT 1
                """,
                (listing.stable_key, listing.normalized_url, listing.fingerprint),
            ).fetchone()
        return row is not None

    def upsert_observed(self, listing: Listing) -> bool:
        """Store a listing and return True when this is the first observation."""
        now = utc_now()
        with self._connect() as connection:
            existed = self._was_observed(connection, listing)
            connection.execute(
                """
                INSERT INTO seen_listings (
                    stable_key, source, external_id, title, url, first_seen_at,
                    normalized_url, fingerprint, price, location, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stable_key) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    normalized_url = excluded.normalized_url,
                    fingerprint = excluded.fingerprint,
                    price = excluded.price,
                    location = excluded.location,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    listing.stable_key,
                    listing.source,
                    listing.external_id,
                    listing.title,
                    listing.url,
                    now,
                    listing.normalized_url,
                    listing.fingerprint,
                    listing.price,
                    listing.location,
                    now,
                ),
            )
        return not existed

    def mark_notified(self, listing: Listing) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE seen_listings
                SET last_notified_at = ?
                WHERE stable_key = ?
                """,
                (utc_now(), listing.stable_key),
            )

    def was_notified(self, listing: Listing) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM seen_listings
                WHERE stable_key = ? AND last_notified_at IS NOT NULL
                LIMIT 1
                """,
                (listing.stable_key,),
            ).fetchone()
        return row is not None

    def stats(self) -> dict[str, int]:
        with self._connect() as connection:
            listings_count = connection.execute("SELECT COUNT(*) FROM seen_listings").fetchone()[0]
            notified_count = connection.execute(
                "SELECT COUNT(*) FROM seen_listings WHERE last_notified_at IS NOT NULL"
            ).fetchone()[0]
            bootstrapped_count = connection.execute(
                "SELECT COUNT(*) FROM search_state WHERE bootstrapped = 1"
            ).fetchone()[0]
        return {
            "listings_count": listings_count,
            "notified_count": notified_count,
            "bootstrapped_count": bootstrapped_count,
        }

    def _was_observed(self, connection: sqlite3.Connection, listing: Listing) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM seen_listings
            WHERE stable_key = ? OR normalized_url = ? OR fingerprint = ?
            LIMIT 1
            """,
            (listing.stable_key, listing.normalized_url, listing.fingerprint),
        ).fetchone()
        return row is not None

    def _add_column(self, connection: sqlite3.Connection, table: str, column_sql: str) -> None:
        try:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
