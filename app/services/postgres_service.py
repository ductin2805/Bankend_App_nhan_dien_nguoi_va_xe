"""PostgreSQL storage helper used by app services."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
except Exception:  # pragma: no cover - package may be absent at import time
    psycopg2 = None
    Json = None
    RealDictCursor = None
    SimpleConnectionPool = None


class PostgresStorage:
    """Small wrapper around psycopg2 with lazy pool and schema bootstrap."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self._pool = None
        self._enabled = bool(self.database_url and psycopg2 and SimpleConnectionPool)
        if self._enabled:
            try:
                self._pool = SimpleConnectionPool(1, 5, dsn=self.database_url)
            except Exception as exc:
                print(f"[postgres] Unable to initialize pool: {exc}")
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._pool is not None)

    @contextmanager
    def connection(self):
        if not self.enabled:
            yield None
            return

        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def init_schema(self) -> None:
        if not self.enabled:
            return

        with self.connection() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history_entries (
                        id TEXT PRIMARY KEY,
                        machine_id TEXT NOT NULL,
                        timestamp DOUBLE PRECISION NOT NULL,
                        type TEXT,
                        method TEXT,
                        path TEXT,
                        summary JSONB,
                        full_result JSONB,
                        representative_image_path TEXT,
                        raw_entry JSONB NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_history_machine_ts
                        ON history_entries (machine_id, timestamp DESC);

                    CREATE TABLE IF NOT EXISTS face_persons (
                        person_id TEXT PRIMARY KEY,
                        owner_machine_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        person_code TEXT,
                        info JSONB NOT NULL DEFAULT '{}'::jsonb,
                        descriptors JSONB NOT NULL DEFAULT '[]'::jsonb,
                        registration_image_path TEXT,
                        created_at DOUBLE PRECISION NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_face_owner
                        ON face_persons (owner_machine_id);
                    """
                )

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        with self.connection() as conn:
            if conn is None:
                return []
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        with self.connection() as conn:
            if conn is None:
                return None
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return dict(row) if row else None

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        if not self.enabled:
            return 0

        with self.connection() as conn:
            if conn is None:
                return 0
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount

    @staticmethod
    def to_json(value: Any) -> Any:
        if Json is None:
            return value
        return Json(value)


postgres_storage = PostgresStorage()
