# drizzle_codegen.py
"""
Generate SQLAlchemy + Pydantic models from drizzle-schema.json.

Assumes:
  - drizzle-schema.json lives at repo root
  - SQLAlchemy models go to:
        backend/nlp/src/lang3s/db/models.py
  - Pydantic models go to:
        backend/nlp/src/lang3s/db/schemas.py

Run:
    python drizzle_codegen.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# -------------------------------------------------------------------
# PATHS / CONFIG
# -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_JSON_PATH = REPO_ROOT / "drizzle-schema.json"

PY_MODELS_PATH = (
    REPO_ROOT
    / "backend"
    / "nlp"
    / "src"
    / "lang3s"
    / "db"
    / "models.py"
)

PY_SCHEMAS_PATH = (
    REPO_ROOT
    / "backend"
    / "nlp"
    / "src"
    / "lang3s"
    / "db"
    / "schemas.py"
)

# Drizzle constructor name -> SQLAlchemy type
DRIZZLE_TO_SQLALCHEMY: Dict[str, str] = {
    "text": "Text",
    "varchar": "String",
    "char": "String",
    "integer": "Integer",
    "serial": "Integer",
    "bigserial": "BigInteger",
    "bigint": "BigInteger",
    "boolean": "Boolean",
    "timestamp": "DateTime",
    "date": "Date",
    "numeric": "Numeric",
    "doublePrecision": "Float",
    "double": "Float",
    "float": "Float",

    "json": "JSON",
    "jsonb": "JSONB",

    # treat ltree as text unless wired to custom type
    "ltree": "Text",

    # pgvector-related
    "vector": "Vector",
    "halfvec": "Vector",
    "bit": "Vector",  # use Vector for hnsw indexes over bit embeddings
}

# Drizzle constructor name -> Pydantic (Python) type
DRIZZLE_TO_PYDANTIC: Dict[str, str] = {
    "text": "str",
    "varchar": "str",
    "char": "str",
    "integer": "int",
    "serial": "int",
    "bigserial": "int",
    "bigint": "int",
    "boolean": "bool",
    "timestamp": "datetime",
    "date": "date",
    "numeric": "float",
    "doublePrecision": "float",
    "double": "float",
    "float": "float",
    "json": "dict",
    "jsonb": "dict",
    "ltree": "str",

    "vector": "list[float]",
    "halfvec": "list[float]",
    "bit": "list[int]",  # adjust if you prefer
}

RESERVED_SQLA_ATTRS = {"metadata", "type", "class", "global", "lambda"}


# -------------------------------------------------------------------
# DATA STRUCTURES
# -------------------------------------------------------------------

@dataclass
class EnumSpec:
    var_name: str  # e.g. "jobStatusEnum"
    db_name: str  # e.g. "job_status"
    values: List[str]


@dataclass
class ForeignKeySpec:
    table_var: str  # TS var name of target table, e.g. "DocumentsTable"
    column: str  # column name on target, e.g. "id"
    on_delete: Optional[str] = None


@dataclass
class ColumnSpec:
    name: str  # TS property name, e.g. "updatedAt"
    db_name: str  # DB column name, e.g. "updated_at"
    drizzle_type: str  # constructor, e.g. "timestamp", "jsonb", "halfvec"
    nullable: bool
    primary_key: bool
    unique: bool
    has_default: bool
    vector_dims: Optional[int] = None
    enum_var: Optional[str] = None
    fk: Optional[ForeignKeySpec] = None


@dataclass
class TableSpec:
    name: str  # DB table name, e.g. "text"
    columns: List[ColumnSpec] = field(default_factory=list)


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------

def camel_case(name: str) -> str:
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p.capitalize() for p in parts)


def guess_parent_table_name(table_var: str, tables: List[TableSpec]) -> str:
    """
    Guess the DB table name from a TS var like "DocumentsTable" or "TextAnnotationsTable".

    Heuristic:
      - strip trailing "Table"/"Tables" (case-insensitive)
      - compare lowercase to existing table names
      - fallback to singular/plural-ish match
    """
    base = table_var
    lower = base.lower()
    if lower.endswith("tables"):
        base = base[:-6]
    elif lower.endswith("table"):
        base = base[:-5]

    simple = base.lower()

    # direct match
    for t in tables:
        if t.name.lower() == simple:
            return t.name

    # singular/plural-ish: compare after stripping trailing 's'
    for t in tables:
        if t.name.lower().rstrip("s") == simple.rstrip("s"):
            return t.name

    # last resort: just return the lowercase base (might not match, but keeps going)
    return simple


def load_schema() -> tuple[List[EnumSpec], List[TableSpec]]:
    data = json.loads(SCHEMA_JSON_PATH.read_text())

    enums_json = data.get("enums", [])
    tables_json = data.get("tables", [])

    enums: List[EnumSpec] = []
    for e in enums_json:
        enums.append(
            EnumSpec(
                var_name=e.get("varName"),
                db_name=e.get("name"),
                values=e.get("values", []),
            )
        )

    tables: List[TableSpec] = []
    for t in tables_json:
        table_name = t.get("tableName")
        cols: List[ColumnSpec] = []

        for c in t.get("columns", []):
            fk_spec = None
            fk_json = c.get("fk")
            if fk_json:
                fk_spec = ForeignKeySpec(
                    table_var=fk_json.get("tableVar", ""),
                    column=fk_json.get("column", "id"),
                    on_delete=fk_json.get("onDelete"),
                )

            col = ColumnSpec(
                name=c.get("name"),
                db_name=c.get("dbName", c.get("name")),
                drizzle_type=c.get("drizzleType"),
                nullable=c.get("nullable", True),
                primary_key=c.get("primaryKey", False),
                unique=c.get("unique", False),
                has_default=c.get("hasDefault", False),
                vector_dims=c.get("vectorDims"),
                enum_var=c.get("enumVar"),
                fk=fk_spec,
            )
            cols.append(col)

        tables.append(TableSpec(name=table_name, columns=cols))

    return enums, tables


# -------------------------------------------------------------------
# SQLALCHEMY GENERATION (WITH RELATIONSHIPS)
# -------------------------------------------------------------------

def render_sqlalchemy(enums: List[EnumSpec], tables: List[TableSpec]) -> str:
    lines: List[str] = []

    lines.append("# AUTOGENERATED FROM drizzle-schema.json. DO NOT EDIT BY HAND.")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append(
        "from sqlalchemy import ("
        "Column, Integer, BigInteger, String, Boolean, DateTime, Date, "
        "Float, Numeric, Text, JSON, Enum, ForeignKey"
        ")"
    )
    lines.append("from sqlalchemy.dialects.postgresql import JSONB")
    lines.append("from sqlalchemy.orm import declarative_base, relationship")
    lines.append("from pgvector.sqlalchemy import Vector")
    lines.append("")
    lines.append("Base = declarative_base()")
    lines.append("")

    enum_by_var: Dict[str, EnumSpec] = {e.var_name: e for e in enums if e.var_name}

    table_name_to_class: Dict[str, str] = {
        t.name: camel_case(t.name) + "Table"
        for t in tables
    }
    # Build parent→children relationship map:
    # { parent_table_name: [(child_table_name, child_fk_attr_name)] }
    parent_to_children: Dict[str, List[tuple[str, str]]] = {}

    for t in tables:
        for col in t.columns:
            if col.fk and col.fk.table_var:
                parent_table = guess_parent_table_name(col.fk.table_var, tables)
                parent_to_children.setdefault(parent_table, []).append((t.name, col.name))

    for table in tables:
        class_name = table_name_to_class[table.name]
        lines.append(f"class {class_name}(Base):")
        lines.append(f"    __tablename__ = '{table.name}'")
        lines.append("")

        # columns
        for col in table.columns:
            # type expression
            if col.enum_var and col.enum_var in enum_by_var:
                enum_spec = enum_by_var[col.enum_var]
                values_repr = ", ".join(repr(v) for v in enum_spec.values)
                type_expr = f"Enum({values_repr}, name={enum_spec.db_name!r})"
            else:
                sa_type = DRIZZLE_TO_SQLALCHEMY.get(col.drizzle_type, "Text")
                if sa_type == "Vector":
                    if col.vector_dims is not None:
                        type_expr = f"Vector({col.vector_dims})"
                    else:
                        type_expr = "Vector()"
                else:
                    type_expr = sa_type

            attr_name = col.name
            if attr_name in RESERVED_SQLA_ATTRS:
                attr_name = attr_name + "_"

            col_args: List[str] = [type_expr]
            col_kwargs: List[str] = []

            # foreign key
            if col.fk and col.fk.table_var:
                parent_table_name = guess_parent_table_name(col.fk.table_var, tables)
                parent_col_name = col.fk.column or "id"
                fk_target = f"{parent_table_name}.{parent_col_name}"
                fk_parts = [repr(fk_target)]
                if col.fk.on_delete:
                    fk_parts.append(f"ondelete={col.fk.on_delete!r}")
                col_args.append(f"ForeignKey({', '.join(fk_parts)})")

            if col.primary_key:
                col_kwargs.append("primary_key=True")
                col_kwargs.append("nullable=False")
            else:
                col_kwargs.append(f"nullable={col.nullable}")

            if col.unique:
                col_kwargs.append("unique=True")

            args_str = ", ".join(col_args + col_kwargs)
            lines.append(
                f"    {attr_name} = Column({col.db_name!r}, {args_str})"
            )

        lines.append("")

        # child → parent relationships (for each FK pointing *from* this table)
        for col in table.columns:
            if col.fk and col.fk.table_var:
                parent_table_name = guess_parent_table_name(col.fk.table_var, tables)
                parent_class = table_name_to_class.get(parent_table_name, camel_case(parent_table_name))

                # e.g. documentId -> document
                attr_name = col.name
                if attr_name.endswith("Id"):
                    rel_name = attr_name[:-2]
                elif attr_name.endswith("_id"):
                    rel_name = attr_name[:-3]
                else:
                    rel_name = attr_name

                # parent collection name will be decided on parent side
                lines.append(
                    f"    {rel_name} = relationship('{parent_class}', back_populates='{table.name}_collection')"
                )

        if table.name in parent_to_children:
            for child_table_name, fk_attr in parent_to_children[table.name]:

                # Class name with Table suffix
                child_class = table_name_to_class.get(child_table_name, camel_case(child_table_name) + "Table")

                # Collection relationship name
                collection_name = f"{child_table_name}_collection"

                # Backref name for child → parent
                if fk_attr.endswith("Id"):
                    child_back_pop = fk_attr[:-2]
                elif fk_attr.endswith("_id"):
                    child_back_pop = fk_attr[:-3]
                else:
                    child_back_pop = fk_attr

                lines.append(
                    f"    {collection_name} = relationship('{child_class}', back_populates='{child_back_pop}', cascade='all, delete-orphan')"
                )

        lines.append("")
        lines.append("    def __repr__(self) -> str:  # pragma: no cover")
        if any(c.name == "id" for c in table.columns):
            lines.append('        return f"<%s id={self.id}>" % self.__class__.__name__')
        else:
            lines.append('        return f"<%s>" % self.__class__.__name__')
        lines.append("")

    return "\n".join(lines)


# -------------------------------------------------------------------
# PYDANTIC GENERATION
# -------------------------------------------------------------------

def render_pydantic(enums: List[EnumSpec], tables: List[TableSpec]) -> str:
    lines: List[str] = []

    lines.append("# AUTOGENERATED FROM drizzle-schema.json. DO NOT EDIT BY HAND.")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Optional, List, Literal")
    lines.append("from datetime import datetime, date")
    lines.append("from pydantic import BaseModel, ConfigDict")
    lines.append("")

    enum_by_var: Dict[str, EnumSpec] = {e.var_name: e for e in enums if e.var_name}

    for table in tables:
        class_name = camel_case(table.name) + "Model"
        lines.append(f"class {class_name}(BaseModel):")
        lines.append("    model_config = ConfigDict(from_attributes=True)")
        lines.append("")

        for col in table.columns:
            # Determine Python type
            if col.enum_var and col.enum_var in enum_by_var:
                enum_spec = enum_by_var[col.enum_var]
                vals = ", ".join(repr(v) for v in enum_spec.values)
                py_type = f"Literal[{vals}]"
            else:
                py_type = DRIZZLE_TO_PYDANTIC.get(col.drizzle_type, "str")

            required = (col.primary_key or not col.nullable) and not col.has_default

            field_name = col.name

            if required:
                lines.append(f"    {field_name}: {py_type}")
            else:
                lines.append(f"    {field_name}: Optional[{py_type}] = None")

        lines.append("")

    return "\n".join(lines)


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main() -> None:
    print(f"[drizzle_codegen] Loading schema from {SCHEMA_JSON_PATH}")
    enums, tables = load_schema()

    print(f"[drizzle_codegen] Found {len(enums)} enum(s) and {len(tables)} table(s).")

    PY_MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PY_SCHEMAS_PATH.parent.mkdir(parents=True, exist_ok=True)

    models_code = render_sqlalchemy(enums, tables)
    schemas_code = render_pydantic(enums, tables)

    PY_MODELS_PATH.write_text(models_code, encoding="utf-8")
    PY_SCHEMAS_PATH.write_text(schemas_code, encoding="utf-8")

    print(f"[drizzle_codegen] Wrote SQLAlchemy models → {PY_MODELS_PATH}")
    print(f"[drizzle_codegen] Wrote Pydantic schemas → {PY_SCHEMAS_PATH}")


if __name__ == "__main__":
    main()
