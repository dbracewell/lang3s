import gc
import json
from contextlib import contextmanager
from typing import Any, Generator, Iterable

import numpy as np
from pgvector.psycopg import register_vector
from psycopg import sql
from sqlalchemy import NullPool, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection, DBAPICursor
from sqlalchemy.orm import sessionmaker

from lang3s import config
from lang3s.data.db.models import Base, ConfigurationTable

engine = create_engine(config.DB_URL, poolclass=NullPool, echo=False, future=True)
session_local = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    register_vector(dbapi_connection)


@contextmanager
def get_session():
    session = session_local()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def transaction(
    raw: bool = False,
):
    if not raw:
        with get_session() as session:
            with session.begin():
                yield session
    else:
        with raw_connection() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()


@contextmanager
def raw_connection() -> Generator[DBAPIConnection, Any, None]:
    raw = engine.raw_connection()
    connection = raw.dbapi_connection

    if connection is None:
        raw.close()
        raise RuntimeError("engine.raw_connection() returned no DBAPI connection")

    try:
        yield connection
    finally:
        raw.close()


@contextmanager
def raw_cursor() -> Generator[DBAPICursor, Any, None]:
    with raw_connection() as connection:
        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()


@contextmanager
def connection(commit=False):
    with engine.connect() as connection:
        try:
            yield connection
            if commit:
                connection.commit()
        except:
            connection.rollback()
            raise
        finally:
            connection.close()


def alias_identifier(ident, alias=None):
    if isinstance(ident, str):
        ident = (ident,)
    if not alias:
        return sql.Identifier(*ident)
    else:
        return sql.Composed(
            [sql.Identifier(*ident), sql.SQL(" AS "), sql.Identifier(alias)]
        )


MAX_INSERT_SIZE = 60000


def refresh_annotation_views():
    with raw_cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY  annotation_counts;")
        cursor.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY  annotation_co_occurrence;"
        )


def create_text_annotation_embedding_index():
    with raw_cursor() as cursor:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS "text_annotation_embedding_index" ON "text_annotations" USING hnsw ("embedding" halfvec_cosine_ops);'
        )


def refresh_topic_views():
    with raw_cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY  topic_sentences;")
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY  topic_documents;")


def execute(stmt):
    with get_session() as session:
        return session.execute(stmt)


def upsert(stmt, indexes: list[Any]):
    with get_session() as session:
        on_conflict_stmt = stmt.on_conflict_do_update(
            index_elements=indexes,
            set_=stmt.excluded.values(),
        )
        return session.execute(on_conflict_stmt)


def insert_many_objects(objects: list[Base]):
    with get_session() as session:
        return session.bulk_save_objects(objects)


def copy_from(
    cursor: DBAPICursor,
    table: str,
    columns: list[str],
    data: Iterable[list[Any]],
):
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(c) for c in columns),
    )

    with cursor.copy(copy_sql) as copy:
        for row in data:
            copy.write_row(row)

    gc.collect()


def get_config_value(config_name: str, default_value: Any | None = None) -> Any:
    with get_session() as session:
        result = (
            session.query(ConfigurationTable)
            .filter(ConfigurationTable.name == config_name)
            .one_or_none()
        )
        if result:
            return result.value
        return default_value


def prepare_value(v: Any) -> Any:
    """Prepare a Python value for PostgreSQL COPY."""
    if v is None:
        return None

    # 1. Handle NumPy arrays first and fast
    if isinstance(v, np.ndarray):
        return np.array2string(
            v,
            separator=",",
            max_line_width=10**9,  # Large int instead of np.inf
            threshold=10**9,  # Ensures NumPy doesn't 'summarize' with ...
        ).replace("\n", "")

    # 2. Standard JSON handling
    if isinstance(v, (dict, list)):
        return json.dumps(v)

    # 3. Fallback for other iterables
    if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
        return list(v)

    return v
