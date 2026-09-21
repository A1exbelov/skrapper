import sqlite3
from pathlib import Path

from skrapper.models import Listing


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

    def is_seen(self, listing: Listing) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM seen_listings WHERE stable_key = ?",
                (listing.stable_key,),
            ).fetchone()
        return row is not None

    def mark_seen(self, listing: Listing) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO seen_listings (
                    stable_key, source, external_id, title, url, first_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.stable_key,
                    listing.source,
                    listing.external_id,
                    listing.title,
                    listing.url,
                    listing.published_or_now.isoformat(),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

