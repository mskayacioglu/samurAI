"""SQLite persistence service for news items, summaries, and ingest runs."""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class StorageService:
    """Persist and query news feed data in a local SQLite database."""

    def __init__(self, db_path: str | None = None):
        default_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "news_data.db")
        self.db_path = db_path or os.getenv("NEWS_DB_PATH", default_db_path)
        self._lock = Lock()
        self._initialize()

    @contextmanager
    def _connect(self):
        """Open a SQLite connection that commits on successful exit."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self):
        """Create required tables and indexes if they do not exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        logger = logging.getLogger("db_audit")
        with self._lock:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS news_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        link TEXT NOT NULL UNIQUE,
                        source_key TEXT NOT NULL,
                        source_name TEXT NOT NULL,
                        language_key TEXT NOT NULL,
                        topic_key TEXT,
                        country_key TEXT,
                        region_key TEXT,
                        title TEXT NOT NULL,
                        published_at TEXT,
                        image_url TEXT,
                        article_text TEXT NOT NULL,
                        fetched_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS news_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        news_item_id INTEGER NOT NULL,
                        model_key TEXT NOT NULL,
                        language_key TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(news_item_id, model_key, language_key),
                        FOREIGN KEY(news_item_id) REFERENCES news_items(id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ingest_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        status TEXT NOT NULL,
                        config_json TEXT NOT NULL,
                        stats_json TEXT,
                        error_message TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_news_items_filters ON news_items(language_key, topic_key, region_key, country_key)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_news_items_published_at ON news_items(published_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_news_items_source_key ON news_items(source_key)"
                )
        logger.info("db_init path=%s", self.db_path)

    def _utc_now(self) -> str:
        """Return the current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def upsert_news_item(self, item: dict[str, Any]) -> tuple[int, bool]:
        """Insert or update one news item and return its id and insert flag."""
        logger = logging.getLogger("db_audit")
        now = self._utc_now()
        published_at = item.get("published_at")
        if hasattr(published_at, "isoformat"):
            published_at = published_at.isoformat()

        with self._lock:
            with self._connect() as conn:
                existing_row = conn.execute(
                    "SELECT id FROM news_items WHERE link = ?",
                    (item["link"],),
                ).fetchone()
                cursor = conn.execute(
                    """
                    INSERT INTO news_items (
                        link, source_key, source_name, language_key, topic_key, country_key, region_key,
                        title, published_at, image_url, article_text, fetched_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        source_key=excluded.source_key,
                        source_name=excluded.source_name,
                        language_key=excluded.language_key,
                        topic_key=excluded.topic_key,
                        country_key=excluded.country_key,
                        region_key=excluded.region_key,
                        title=excluded.title,
                        published_at=COALESCE(excluded.published_at, news_items.published_at),
                        image_url=COALESCE(NULLIF(excluded.image_url, ''), news_items.image_url),
                        article_text=COALESCE(NULLIF(excluded.article_text, ''), news_items.article_text),
                        fetched_at=excluded.fetched_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        item["link"],
                        item["source_key"],
                        item["source_name"],
                        item["language_key"],
                        item.get("topic_key", ""),
                        item.get("country_key", ""),
                        item.get("region_key", ""),
                        item["title"],
                        published_at,
                        item.get("image_url", ""),
                        item.get("article_text", ""),
                        now,
                        now,
                    ),
                )
                if existing_row:
                    logger.info(
                        "news_item_upsert action=update id=%s source_key=%s link=%s",
                        existing_row["id"],
                        item["source_key"],
                        item["link"][:400],
                    )
                    return int(existing_row["id"]), False
                logger.info(
                    "news_item_upsert action=insert id=%s source_key=%s link=%s",
                    cursor.lastrowid,
                    item["source_key"],
                    item["link"][:400],
                )
                return int(cursor.lastrowid), True

    def upsert_summary(self, news_item_id: int, model_key: str, language_key: str, summary: str):
        """Insert or update a model summary for a stored news item."""
        logger = logging.getLogger("db_audit")
        now = self._utc_now()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO news_summaries (news_item_id, model_key, language_key, summary, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(news_item_id, model_key, language_key) DO UPDATE SET
                        summary=excluded.summary,
                        updated_at=excluded.updated_at
                    """,
                    (news_item_id, model_key, language_key, summary, now, now),
                )
        logger.info(
            "summary_upsert news_item_id=%s model=%s language=%s summary_chars=%s",
            news_item_id,
            model_key,
            language_key,
            len(summary or ""),
        )

    def get_summary(self, news_item_id: int, model_key: str, language_key: str) -> str:
        """Return one stored summary or an empty string when it is missing."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT summary
                FROM news_summaries
                WHERE news_item_id = ? AND model_key = ? AND language_key = ?
                LIMIT 1
                """,
                (news_item_id, model_key, language_key),
            ).fetchone()
        return row["summary"] if row else ""

    def fetch_news_items(
        self,
        language_key: str,
        topic_key: str,
        country_key: str,
        region_key: str,
        selected_sources: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch stored news items filtered by language, topic, and sources."""
        clauses = ["language_key = ?"]
        params: list[Any] = [language_key]

        if topic_key:
            clauses.append("topic_key = ?")
            params.append(topic_key)
        if country_key:
            clauses.append("country_key = ?")
            params.append(country_key.upper())
        if region_key:
            clauses.append("region_key = ?")
            params.append(region_key)
        if selected_sources:
            placeholders = ",".join(["?"] * len(selected_sources))
            clauses.append(f"source_key IN ({placeholders})")
            params.extend(selected_sources)

        sql = (
            "SELECT id, link, source_key, source_name, language_key, title, published_at, image_url, article_text "
            "FROM news_items "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY COALESCE(published_at, fetched_at) DESC "
            "LIMIT ?"
        )
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        return [dict(row) for row in rows]

    def fetch_news_items_with_summary(
        self,
        language_key: str,
        model_key: str,
        topic_key: str,
        country_key: str,
        region_key: str,
        selected_sources: list[str],
        keyword: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch stored news items joined with a selected model summary."""
        clauses = [
            "ni.language_key = ?",
            "ns.model_key = ?",
            "ns.language_key = ?",
        ]
        params: list[Any] = [language_key, model_key, language_key]

        if topic_key:
            clauses.append("ni.topic_key = ?")
            params.append(topic_key)
        if country_key:
            clauses.append("ni.country_key = ?")
            params.append(country_key.upper())
        if region_key:
            clauses.append("ni.region_key = ?")
            params.append(region_key)
        if selected_sources:
            placeholders = ",".join(["?"] * len(selected_sources))
            clauses.append(f"ni.source_key IN ({placeholders})")
            params.extend(selected_sources)
        if keyword:
            clauses.append(
                "(ni.title LIKE ? COLLATE NOCASE OR ns.summary LIKE ? COLLATE NOCASE OR ni.article_text LIKE ? COLLATE NOCASE)"
            )
            keyword_like = f"%{keyword}%"
            params.extend([keyword_like, keyword_like, keyword_like])

        sql = (
            "SELECT ni.id, ni.link, ni.source_key, ni.source_name, ni.language_key, ni.title, "
            "ni.published_at, ni.image_url, ni.article_text, ns.summary "
            "FROM news_items ni "
            "INNER JOIN news_summaries ns ON ns.news_item_id = ni.id "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY COALESCE(ni.published_at, ni.fetched_at) DESC "
            "LIMIT ?"
        )
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        return [dict(row) for row in rows]

    def start_ingest_run(self, config: dict[str, Any]) -> int:
        """Persist the start of an ingest run and return its run id."""
        logger = logging.getLogger("db_audit")
        started_at = self._utc_now()
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO ingest_runs (started_at, status, config_json)
                    VALUES (?, ?, ?)
                    """,
                    (started_at, "running", json.dumps(config, ensure_ascii=False)),
                )
                run_id = int(cursor.lastrowid)
                logger.info("ingest_run_start id=%s config=%s", run_id, json.dumps(config, ensure_ascii=False))
                return run_id

    def finish_ingest_run(
        self,
        run_id: int,
        status: str,
        stats: dict[str, Any],
        error_message: str = "",
    ):
        """Persist final status, stats, and errors for an ingest run."""
        logger = logging.getLogger("db_audit")
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE ingest_runs
                    SET finished_at = ?, status = ?, stats_json = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (
                        self._utc_now(),
                        status,
                        json.dumps(stats, ensure_ascii=False),
                        error_message,
                        run_id,
                    ),
                )
        logger.info(
            "ingest_run_finish id=%s status=%s error=%s stats=%s",
            run_id,
            status,
            (error_message or "")[:300],
            json.dumps(stats, ensure_ascii=False),
        )

    def get_latest_ingest_run(self) -> dict[str, Any]:
        """Return the most recent ingest run with decoded config and stats."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, started_at, finished_at, status, config_json, stats_json, error_message "
                "FROM ingest_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if not row:
            return {}

        result = dict(row)
        result["config"] = json.loads(result.pop("config_json") or "{}")
        result["stats"] = json.loads(result.pop("stats_json") or "{}")
        return result
