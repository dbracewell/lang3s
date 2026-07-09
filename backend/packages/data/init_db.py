import asyncio
import json
import random
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy_utils import Ltree

from lang3s.core.clients import RedisClient
from lang3s.core.collections_extras import hashed_select
from lang3s.core.constants import COLOR_NAMES
from lang3s.data.db import session_manager
from lang3s.data.filestore import filestore
from lang3s.data.models import AnnotationOntologyMapping, Base, Ontology


async def nuke_database(conn):
    print("☢️ Nuking the public schema...")
    await conn.execute(text("DROP SCHEMA public CASCADE;"))
    await conn.execute(text("CREATE SCHEMA public;"))
    await conn.execute(text("GRANT ALL ON SCHEMA public TO admin;"))
    await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    print("✅ Schema wiped clean. The database is a blank slate.")


def clear_redis():
    print("Clearing Redis...", end=" ")
    with RedisClient() as client:
        client.flush_all()
    print("Done.")


def clear_analytics_db():
    print("Clearing Analytics DB...", end=" ")
    db_file = filestore.get_analytics_db_path()
    if db_file.exists():
        db_file.unlink()
    print("Done.")


async def load_ontology():
    print("Loading ontology...")
    root_node = Ontology(
        name="ALL",
        path=Ltree("ALL"),
        description="The root of the ontology.",
        color=random.choice(COLOR_NAMES),
    )
    for file in ["entity_ontology.json", "verb_ontology.json"]:
        with open(f"./data/{file}") as f:
            for key, value in json.load(f).items():
                _walk_tree(root_node, key, value)

    async with session_manager.session() as session:
        session.add(root_node)
        await session.flush()
        await session.commit()


def _walk_tree(
    parent: Ontology,
    node_name: str,
    node_info: dict[str, Any],
):
    new_node = Ontology(
        name=node_name,
        path=Ltree(f"{parent.path}.{node_name}"),
        description=node_info.get("description", None),
        properties=node_info.get("properties", {}),
        color=hashed_select(node_name, COLOR_NAMES),
        parent=parent,
    )

    raw_mappings = set(node_info.get("mappings", []))
    path = new_node.path.path.split(".")[1:]
    if len(path) > 1:
        raw_mappings.add(f"{path[0].lower()}:{node_name}")

    for m in raw_mappings:
        mapping_instance = AnnotationOntologyMapping(mapping=m)
        new_node.mappings.append(mapping_instance)

    parent.children.append(new_node)

    children_list = node_info.get("children", [])
    for child_dict in children_list:
        child_name = child_dict.get("name")
        if child_name:
            _walk_tree(new_node, child_name, child_dict)


async def create_hash_partitions(conn, table_name: str, modulus: int = 4):
    """
    Dynamically creates Hash partitions for a given table.
    modulus: The total number of partitions to split the data into.
    """
    print(f"Generating {modulus} hash partitions for '{table_name}'...")
    for i in range(modulus):
        partition_name = f"{table_name}_part_{i}"

        # PostgreSQL syntax for Hash partitioning
        sql = f"""
            CREATE TABLE IF NOT EXISTS {partition_name} 
            PARTITION OF {table_name} 
            FOR VALUES WITH (MODULUS {modulus}, REMAINDER {i});
        """
        await conn.execute(text(sql))
    print(f"Partitions for '{table_name}' created successfully.")


async def init_database():
    print("Creating database schema...")

    session_manager.init()
    async with session_manager.connect() as conn:
        # Nuke old data
        await nuke_database(conn)

        # Enable required PostgreSQL extensions
        print("Ensuring database extensions are created...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgroonga;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS ltree;"))

        # Pust all Tables and Schema events
        print("Pushing tables and functions...")
        await conn.run_sync(Base.metadata.create_all)

        # Create TextAnnotation Partitions
        print("Building TextAnnotation hash partitions...")
        await create_hash_partitions(conn, "text_annotations", modulus=10)

    # Load Ontology
    await load_ontology()

    print("Database initialization complete.")


def stamp_alembic():
    print("Stamping Alembic 'head'...")
    alembic_cfg = Config("alembic.ini")
    command.stamp(alembic_cfg, "head")
    print("Alembic successfully stamped!")


if __name__ == "__main__":
    asyncio.run(init_database())
    stamp_alembic()
    clear_redis()
    clear_analytics_db()
