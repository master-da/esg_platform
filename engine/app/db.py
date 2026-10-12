"""Database access.

Every request runs in ONE transaction that carries the caller's verified JWT claims, so
Postgres RLS policies and audit triggers see the real user (auth.uid()).

* By default the transaction runs as role `authenticated` -> RLS applies exactly as it would
  for a direct PostgREST call. Use it for reads and for authorisation checks.
* `with tx.privileged():` switches back to the `engine_app` role (BYPASSRLS) for writes the
  engine has already authorised (calculations, file reviews, records ...). Claims stay set,
  so audit rows still record the acting user.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


class Tx:
    def __init__(self, conn: Connection, claims: dict[str, Any] | None):
        self.conn = conn
        self.claims = claims
        self._privileged_depth = 0

    # -- role switching -------------------------------------------------------------
    def _as_user(self) -> None:
        if self.claims is not None:
            self.conn.execute("set local role authenticated")

    @contextmanager
    def privileged(self) -> Iterator[Tx]:
        self._privileged_depth += 1
        self.conn.execute("reset role")
        try:
            yield self
        finally:
            self._privileged_depth -= 1
            if self._privileged_depth == 0:
                self._as_user()

    # -- query helpers --------------------------------------------------------------
    def all(self, sql: str, params: Any = None) -> list[dict[str, Any]]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: Any = None) -> dict[str, Any] | None:
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Any = None) -> Any:
        row = self.conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return next(iter(row.values()))

    def execute(self, sql: str, params: Any = None) -> None:
        self.conn.execute(sql, params)

    def log_event(self, company_id: str | None, entity: str, entity_id: str | None, action: str,
                  detail: dict[str, Any] | None = None) -> None:
        with self.privileged():
            self.conn.execute(
                "select app.log_event(%s, %s, %s, %s, %s::jsonb)",
                (company_id, entity, entity_id, action, json.dumps(detail, default=str) if detail else None),
            )


@contextmanager
def transaction(claims: dict[str, Any] | None) -> Iterator[Tx]:
    """Open a transaction for a verified user (claims) or for a system job (claims=None)."""
    with pool().connection() as conn:
        with conn.transaction():
            conn.execute("select set_config('app.source', 'engine', true)")
            if claims is not None:
                conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
            tx = Tx(conn, claims)
            tx._as_user()
            yield tx
