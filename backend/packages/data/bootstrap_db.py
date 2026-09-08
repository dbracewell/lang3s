import asyncio

from init_db import create_hash_partitions, load_ontology
from sqlalchemy import select, text

from lang3s.data.db import session_manager
from lang3s.data.models import Base, Ontology


async def bootstrap_database():
    print("Bootstrapping database schema (non-destructive)...")
    session_manager.init()

    async with session_manager.connect() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgroonga;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS ltree;"))
        await conn.run_sync(Base.metadata.create_all)
        await create_hash_partitions(conn, "text_annotations", modulus=10)

    async with session_manager.session() as session:
        existing_root = await session.scalar(select(Ontology.id).limit(1))

    if existing_root is None:
        print("Ontology is empty; loading seed ontology...")
        await load_ontology()
    else:
        print("Ontology already seeded; skipping load.")

    await session_manager.close()
    print("Database bootstrap complete.")


if __name__ == "__main__":
    asyncio.run(bootstrap_database())
