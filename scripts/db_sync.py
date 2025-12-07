# drizzle_codegen.py
"""
Generate SQLAlchemy + Pydantic models from drizzle-schema.json.

Assumes:
  - drizzle-schema.json lives at repo root
  - SQLAlchemy models should go to:
        backend/nlp/src/lang3s/db/models.py
  - Pydantic models should go to:
        backend/nlp/src/lang3s/db/schemas.py

Run:
    python drizzle_codegen.py
"""

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

    # treat ltree as text unless you wire a custom type
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
    "bit": "list[int]",  # adjust to list[bool] or bytes if you prefer
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
    table_var: str  # TS var name of target table, e.g. "UsersTable"
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
    var_name: Optional[str] = None  # TS var name, if present in JSON
    columns: List[ColumnSpec] = field(default_factory=list)


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------

def camel_case(name: str) -> str:
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p.capitalize() for p in parts)


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

    var_name_to_enum: Dict[str, EnumSpec] = {
        e.var_name: e for e in enums if e.var_name
    }

    tables: List[TableSpec] = []
    for t in tables_json:
        table_name = t.get("tableName")
        var_name = t.get("varName")  # may be missing if extractor doesn't set it
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

        tables.append(TableSpec(name=table_name, var_name=var_name, columns=cols))

    # Attach enum specs by enum_var name if needed (we already keyed them)
    # For now, we just pass enums + columns referencing them by name.

    return enums, tables


# -------------------------------------------------------------------
# SQLALCHEMY GENERATION
# -------------------------------------------------------------------

def render_sqlalchemy(enums: List[EnumSpec], tables: List[TableSpec]) -> str:
    lines: List[str] = []

    lines.append("# AUTOGENERATED FROM drizzle-schema.json. DO NOT EDIT BY HAND.")
    lines.append("")
    lines.append(
        "from sqlalchemy import ("
        "Column, Integer, BigInteger, String, Boolean, DateTime, Date, "
        "Float, Numeric, Text, JSON, Enum, ForeignKey"
        ")"
    )
    lines.append("from sqlalchemy.dialects.postgresql import JSONB")
    lines.append("from sqlalchemy.orm import declarative_base")
    lines.append("from pgvector.sqlalchemy import Vector")
    lines.append("")
    lines.append("Base = declarative_base()")
    lines.append("")

    # Build mapping from TS var_name -> DB table name (if available)
    table_name_by_var: Dict[str, str] = {}
    for t in tables:
        if t.var_name:
            table_name_by_var[t.var_name] = t.name

    # Enums: can be inlined in columns, so no need to define SQLAlchemy EnumTypes
    enum_by_var: Dict[str, EnumSpec] = {e.var_name: e for e in enums if e.var_name}

    for table in tables:
        class_name = camel_case(table.name) + "Table"
        lines.append(f"class {class_name}(Base):")
        lines.append(f"    __tablename__ = '{table.name}'")
        lines.append("")

        for col in table.columns:
            # Determine type expression
            type_expr: str

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

            # Python attribute name; handle reserved names
            attr_name = col.name
            if attr_name in RESERVED_SQLA_ATTRS:
                attr_name = attr_name + "_"

            # Build Column parameters
            col_args: List[str] = [type_expr]
            col_kwargs: List[str] = []

            # Foreign key if we have mapping
            if col.fk and col.fk.table_var:
                target_table = table_name_by_var.get(col.fk.table_var, col.fk.table_var)
                target_col = col.fk.column or "id"
                fk_target = f"{target_table}.{target_col}"
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

            # Note: we are not rendering server_default; DB handles actual default.
            # You can add this later if you want to reflect default expressions.

            args_str = ", ".join(col_args + col_kwargs)
            lines.append(
                f"    {attr_name} = Column({col.db_name!r}, {args_str})"
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

            # Required or optional: primary_key or (not nullable and no default)
            required = (col.primary_key or not col.nullable) and not col.has_default

            # Keep original column name in Pydantic (even if SQLAlchemy attr has "_")
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
