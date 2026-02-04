from pgvector.psycopg import register_vector
from sqlalchemy import NullPool, PoolProxiedConnection, create_engine, event
from sqlalchemy.orm import sessionmaker

from lang3s import config
from lang3s.app import Application

engine = create_engine(config.DB_URL, poolclass=NullPool, echo=False, future=True)
session_local = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    register_vector(dbapi_connection)


class Test(Application):
    def run(self):
        raw = engine.raw_connection()
        with raw.dbapi_connection as conn:  # type: ignore
            with conn.cursor() as cur:
                r = cur.execute(
                    "select embedding from lang3s.public.text_annotations limit 1"
                ).fetchall()
                for row in r:
                    print(type(row[0]))


if __name__ == "__main__":
    Test.from_cli().run()
