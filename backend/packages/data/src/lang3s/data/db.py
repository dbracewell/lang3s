import asyncio
import re
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Type, TypeVar

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from lang3s.core import config
from lang3s.data.models import Base
from lang3s.data.repositories.ontology_repository import OntologyRepository
from lang3s.data.schemas import Ontology


class DatabaseSessionManager:
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker[AsyncSession]] = None
        self._bound_loop = None

    def init(self):
        self._bound_loop = asyncio.get_running_loop()
        if self._engine is None:
            db_url = config.DB_URL
            if "postgresql+asyncpg:" not in db_url:
                db_url = re.sub(
                    r"^postgresql(\+[^:]+)?:", "postgresql+asyncpg:", db_url
                )
            self._engine = create_async_engine(db_url)
        if self._session_maker is None:
            self._session_maker = async_sessionmaker(
                expire_on_commit=False,
                bind=self._engine,
            )

    def is_current_loop(self) -> bool:
        """Check if the current executing loop matches the DB loop."""
        if self._bound_loop is None:
            return True

        try:
            return asyncio.get_running_loop() is self._bound_loop
        except RuntimeError:
            return False

    @property
    def is_initialized(self) -> bool:
        return self._engine is not None

    async def close(self) -> None:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()

        self._engine = None
        self._session_maker = None

    @asynccontextmanager
    async def connect(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            yield connection

    @asynccontextmanager
    async def session(self):
        if self._session_maker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._session_maker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class SyncDatabaseSessionManager:
    def __init__(self) -> None:
        self._engine: Optional[Engine] = None
        self._session_maker: Optional[sessionmaker[Session]] = None

    def init(self):
        if self._engine is None:
            db_url = config.DB_URL
            if "postgresql+psycopg:" not in db_url:
                db_url = re.sub(
                    r"^postgresql(\+[^:]+)?:", "postgresql+psycopg:", db_url
                )
            self._engine = create_engine(db_url)
        if self._session_maker is None:
            self._session_maker = sessionmaker(
                expire_on_commit=False,
                bind=self._engine,
            )

    @property
    def is_initialized(self) -> bool:
        return self._engine is not None

    def close(self) -> None:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        self._engine.dispose()

        self._engine = None
        self._session_maker = None

    @contextmanager
    def connect(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        with self._engine.begin() as connection:
            yield connection

    @contextmanager
    def session(self):
        if self._session_maker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._session_maker()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


session_manager = DatabaseSessionManager()
sync_session_manager = SyncDatabaseSessionManager()

_ontology: Ontology | None = None
_lock = threading.Lock()


def get_ontology(refresh: bool = False) -> Ontology:
    global _ontology
    _lock.acquire()
    try:
        if refresh or _ontology is None:
            with sync_db_session() as session:
                _ontology = OntologyRepository(session).sync_load_ontology()
        return _ontology  # type: ignore
    finally:
        _lock.release()


async def get_db_session():
    async with session_manager.session() as session:
        yield session


@contextmanager
def sync_db_session(autocommit: bool = False):
    sync_session_manager.init()
    with sync_session_manager.session() as session:
        try:
            yield session
            if autocommit:
                session.commit()
        except Exception:
            session.rollback()
            raise


@asynccontextmanager
async def async_db_session(autocommit: bool = False):
    if not session_manager.is_current_loop():
        temp = DatabaseSessionManager()
    else:
        temp = session_manager
    temp.init()
    async with temp.session() as session:
        try:
            yield session
            if autocommit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise


T = TypeVar("T", bound=Base)


async def drop_indexes(
    table: Type[T],
    indexes: list[str],
):
    async with async_db_session() as session:
        try:
            indexes_set = set(indexes)
            conn = await session.connection()
            for index in table.__table__.indexes:  # type: ignore
                if index.name in indexes_set:
                    await conn.run_sync(index.drop)
            await session.commit()
        except Exception as e:
            if "does not exist" in str(e):
                return
            raise


async def create_indexes(
    table: Type[T],
    indexes: list[str],
):
    async with async_db_session() as session:
        try:
            indexes_set = set(indexes)
            conn = await session.connection()
            for index in table.__table__.indexes:  # type: ignore
                if index.name in indexes_set:
                    await conn.run_sync(index.create)
            await session.commit()
        except Exception as e:
            if "already exists" in str(e):
                return
            raise
