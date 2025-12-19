import json
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple, Dict, Generator, ContextManager

from pgvector.psycopg import register_vector
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker, Session

from lang3s import config
from lang3s.db.models import Base, ConfigurationTable
from lang3s.utils.meta import SingletonMeta


def alias_identifier(ident, alias=None):
    if isinstance(ident, str):
        ident = (ident,)
    if not alias:
        return sql.Identifier(*ident)
    else:
        return sql.Composed(
            [sql.Identifier(*ident), sql.SQL(" AS "), sql.Identifier(alias)]
        )


@contextmanager
def psy_raw(engine):
    raw = engine.raw_connection()
    try:
        yield raw.connection  # yield psycopg3 connection
    finally:
        raw.close()


MAX_INSERT_SIZE = 60000


class Database(metaclass=SingletonMeta):

    def __init__(self) -> None:
        self.engine = create_engine(config.DB_URL, echo=False, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

        @event.listens_for(self.engine, "connect")
        def connect(dbapi_connection, connection_record):
            register_vector(dbapi_connection)

    @contextmanager
    def cursor(self):
        with psy_raw(self.engine) as conn:
            register_vector(conn)
            with conn.cursor() as cursor:
                yield cursor
            conn.commit()

    @contextmanager
    def connection(self, commit=False):
        with self.engine.connect() as connection:
            yield connection
            if commit:
                connection.commit()

    @contextmanager
    def session(self, commit=False):
        with self.SessionLocal() as session:
            yield session
            if commit:
                session.commit()

    def execute(self, stmt, commit=False):
        with self.connection(commit) as session:
            return session.execute(stmt)

    def add(self, stmt):
        with self.session(commit=True) as session:
            return session.add(stmt)

    def upsert(self, stmt, index: str, set_values: Dict[str, Any]):
        with self.connection(commit=True) as session:
            on_conflict_stmt = stmt.on_conflict_do_update(
                index_elements=[index],
                set_=set_values,
            )
            return session.execute(on_conflict_stmt)

    def insert_many_objects(self, objects: List[Base]):
        with self.session(commit=True) as session:
            return session.bulk_save_objects(objects)

    def insert_many_mappings(self, table: Base, values: List[Dict[str, Any]]):
        with self.session(commit=True) as session:
            return session.bulk_insert_mappings(table, values)

    @contextmanager
    def transaction(
        self,
        raw_connection: bool = False,
    ):
        if not raw_connection:
            with self.SessionLocal.begin() as tx:
                yield tx
                tx.commit()
        else:
            with psy_raw(self.engine) as connection:
                register_vector(connection)
                with connection.cursor() as cursor:
                    with connection.transaction():
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
        with self.SessionLocal() as session:
            result = session.query(ConfigurationTable).filter(ConfigurationTable.name == config_name).one_or_none()
            if result:
                return result.value
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
