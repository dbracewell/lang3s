import json
import math
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple

from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import lang3s.config as config
from lang3s.utils import partition


def alias_identifier(ident, alias=None):
    if isinstance(ident, str):
        ident = (ident,)
    if not alias:
        return sql.Identifier(*ident)
    else:
        return sql.Composed(
            [sql.Identifier(*ident), sql.SQL(" AS "), sql.Identifier(alias)]
        )


class Database:
    MAX_INSERT_SIZE = 60000
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.pool = ConnectionPool(
                f"host={config.DB_HOST} dbname=lang3s user={config.DB_USER} password={config.DB_PASSWORD} port={config.DB_PORT}",
                kwargs={"autocommit": True, "row_factory": dict_row},
            )

    @contextmanager
    def cursor(self):
        with self.pool.connection() as connection:
            register_vector(connection)
            with connection.cursor() as cursor:
                yield cursor
            connection.commit()

    @contextmanager
    def transaction(
        self,
    ):
        with self.pool.connection() as connection:
            register_vector(connection)
            with connection.cursor() as cursor:
                yield cursor
            connection.commit()

    def select(
        self,
        table: str,
        columns: List[str],
        where: Optional[List[Tuple[str, str, Any]]] = None,
    ):
        with self.cursor() as cursor:
            whereClause = sql.Literal("TRUE")
            if where and len(where) > 0:
                whereClause = sql.SQL(" and ").join(
                    sql.Composed(
                        [
                            sql.Identifier(column),
                            sql.SQL(operator),  # type: ignore
                            sql.Literal(value),
                        ]
                    )
                    for column, operator, value in where
                )
            query = sql.SQL("SELECT {} FROM {} WHERE {}").format(
                sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                sql.Identifier(table),
                whereClause,
            )
            cursor.execute(query)
            return cursor.fetchall()

    def insert_many(
        self, cursor, table: str, columns: List[str], data: List[Tuple[Any]]
    ):
        insert_size = math.floor(Database.MAX_INSERT_SIZE / len(columns))
        for rows in partition(data, size=insert_size):
            query = sql.SQL("INSERT INTO {} ({}) VALUES {}").format(
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                sql.SQL("({})").format(
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns)
                ),
            )
            cursor.executemany(query, rows)

    def copy_from(
        self,
        cursor,
        table: str,
        columns: List[str],
        data: List[List[Any]],
    ):
        copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        )
        with cursor.copy(copy_sql) as copy:
            for row in data:
                values = [prepare_value(item) for item in row]
                copy.write_row(values)

    def get_config_value(
        self, config_name: str, default_value: Optional[Any] = None
    ) -> Any:
        with self.cursor() as cursor:
            cursor.execute(
                "SELECT value FROM configuration where name=%s",
                [config_name],
            )
            row = cursor.fetchone()
            if row:
                return row["value"]
            return default_value


def prepare_value(v: Any) -> Any:
    """Prepare a Python value for PostgreSQL COPY."""
    if v is None:
        return None
    elif isinstance(v, (dict, list)):
        return json.dumps(v)  # proper JSON encoding
    elif hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
        # likely a pgvector or numpy array
        return "[" + ", ".join(map(str, v)) + "]"
    else:
        return v
