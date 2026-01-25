import gzip
import json
import math
import os
import tempfile
import traceback
from threading import Thread
from typing import Literal

import duckdb
import numpy as np
from _duckdb import DuckDBPyConnection
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lang3s.data.db.filestore import FILE_STORE
from lang3s.services.client.redis_client import DUCKDB_QUEUE_NAME, redis_batch_generator
from lang3s.shared_types.document import Document

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

BATCH_TIMEOUT = 30

connection: DuckDBPyConnection = None


def db_worker():
    global connection
    try:
        for batch in redis_batch_generator(DUCKDB_QUEUE_NAME, 200):
            if batch:
                if (
                    len(batch) == 1
                    and isinstance(batch[0], dict)
                    and batch[0].get("status", "") == "completed"
                ):
                    connection.execute(
                        "PRAGMA create_fts_index('text_annotations', 'id', 'text', overwrite=1);"
                    )
                    connection.commit()
                    continue

                print(f"WRITING {len(batch)} documents to duckdb")
                temp_file = None
                with tempfile.NamedTemporaryFile(
                    mode="w+t", delete=False, suffix=".json"
                ) as f:
                    annotations = []
                    for doc_id in batch:
                        doc = FILE_STORE.read_document(doc_id)
                        for annotation in doc.text.all_annotations:
                            if annotation.type == "token":
                                continue
                            annotations.append(
                                {
                                    "id": annotation.id,
                                    "text": annotation.get(
                                        "coref_text", annotation.text
                                    ).upper(),
                                    "surface": annotation.get(
                                        "coref_text", annotation.text
                                    ),
                                    "type": annotation.type,
                                    "mapping": f"{annotation.type}:{annotation.value}",
                                    "value": annotation.value,
                                    "sentence_aid": annotation.sentence.id,
                                    "document_id": annotation.doc_id,
                                    "embedding": annotation.embedding.tolist(),
                                    "metadata": annotation.metadata(),
                                }
                            )
                    json.dump(annotations, f)
                    f.close()
                    temp_file = f.name
                    connection.execute(
                        f"COPY text_annotations FROM '{temp_file}' (AUTO_DETECT true);"
                    )
                os.remove(temp_file)
                connection.commit()
    except KeyboardInterrupt:
        connection.close()


def init_connection():
    global connection

    connection = duckdb.connect(FILE_STORE.get_analytics_db_path())
    connection.load_extension("json")
    connection.load_extension("fts")
    connection.load_extension("postgres")
    connection.execute(
        f"""ATTACH 'host=192.168.0.100 port=5432 dbname=lang3s user=admin password=abba' AS pg_db (TYPE postgres);"""
    )
    connection.execute("""
                 CREATE TABLE IF NOT EXISTS text_annotations
                 (
                     id           TEXT PRIMARY KEY,
                     text         TEXT,
                     surface      TEXT,
                     type         TEXT,
                     mapping      TEXT,
                     value        TEXT,
                     sentence_aid TEXT,
                     document_id  TEXT,
                     embedding    FLOAT[384],
                     metadata     JSON
                 )
                 """)

    connection.execute("""
CREATE VIEW IF NOT EXISTS text_annotations_mapped
AS (
 select a.*, o.name as name, o.path as path, CONCAT(a.text,'-',o.path)as normalized_path
   from text_annotations a
   inner join pg_db.public.annotation_to_ontology ato on a.mapping = ato.annotation_type_value
   inner join pg_db.public.ontology o on ato.ontology_id = o.id
 )
                 """)

    connection.execute("""
CREATE VIEW IF NOT EXISTS text_annotations_mapped_counts AS
WITH ta_mapped AS (
    select a.*, o.name as name, o.path as path, CONCAT(a.text,'-',o.path)as normalized_path
   from text_annotations a
   inner join pg_db.public.annotation_to_ontology ato on a.mapping = ato.annotation_type_value
   inner join pg_db.public.ontology o on ato.ontology_id = o.id
) 
select a.*, mention_count, sentence_count, document_count, mentions_per_document
from ta_mapped a
inner join (
 select text, path,
      count(*) as mention_count,
      count(distinct document_id) as document_count,
      count(distinct sentence_aid) as sentence_count,
      count(*) / count(distinct document_id) as mentions_per_document,
from ta_mapped
group by text, path
) b on a.text = b.text and a.path = b.path
                 """)
    thread = Thread(
        target=db_worker,
    )
    thread.start()


class BaseRequest(BaseModel):
    mappings: list[str]
    page: int
    page_size: int
    order_by: Literal["mentions", "docs", "mentionsPerDoc"] = "mentions"


def create_path_match(path_column: str, paths: list[str]):
    where_stmt = []
    for mapping in paths:
        where_stmt.append(f"{path_column} like '{mapping}%'")

    return where_stmt


@router.post("/counts")
async def counts(request: BaseRequest):
    global connection
    try:
        where_stmt = create_path_match("path", request.mappings)

        total = connection.execute(
            f"SELECT COUNT(0) "
            f"FROM ("
            f"  SELECT text,path, count(DISTINCT document_id) "
            f"  FROM text_annotations_mapped "
            f"  where {' OR '.join(where_stmt) if where_stmt else True} "
            f"  GROUP BY text,path HAVING count(DISTINCT document_id) >= 10 ) a"
        ).fetchone()[0]

        order_by_col = "mention_count"
        if request.order_by == "mentionsPerDoc":
            order_by_col = "mentions_per_document"
        elif request.order_by == "docs":
            order_by_col = "document_count"

        result = (
            connection.execute(
                f"""
select DISTINCT text as content, path, mention_count as count, document_count as docCount, sentence_count as sentenceCount, mentions_per_document as mentionsPerDocument,name as value 
from text_annotations_mapped_counts
where ({" OR ".join(where_stmt) if where_stmt else True}) AND document_count > 5 
order by {order_by_col} desc, text, path
offset  ?
limit ?
                   """,
                [
                    (request.page - 1) * request.page_size,
                    request.page_size + 1,
                ],
            )
            .df()
            .to_dict(orient="records")
        )
        return {
            "total": total,
            "totalPages": math.ceil(total / request.page_size),
            "results": result,
        }
    except Exception as e:
        return JSONResponse(content=str(e), status_code=500)


class CoOccurrenceRequest(BaseModel):
    entity: str
    value: str
    targets: list[str]


@router.post("/cooccurrence")
async def cooccurrence(request: CoOccurrenceRequest):
    global connection
    try:
        where_stmt = create_path_match("e2.path", request.targets)

        result = (
            connection.execute(
                f"""
SELECT e2.text as e2, e2.name as e2Type, count(DISTINCT e2.sentence_aid) as count,
FROM text_annotations_mapped e1
INNER JOIN text_annotations_mapped e2 on e1.sentence_aid = e2.sentence_aid  and e1.normalized_path != e2.normalized_path
where ({" OR ".join(where_stmt) if where_stmt else True}) and e1.path = ? and e1.text = ?
group by e2.text, e2.name
order by count(DISTINCT e2.sentence_aid) desc
limit 50
                   """,
                [request.value, request.entity],
            )
            .df()
            .to_dict(orient="records")
        )
        return result
    except Exception as e:
        return JSONResponse(content=str(e), status_code=500)


class EventRequest(BaseModel):
    entity: str
    value: str


@router.post("/events")
async def events(request: EventRequest):
    global connection
    try:
        result = (
            connection.execute(
                f"""
                WITH entity_sentences AS (
                    select DISTINCT e2.sentence_aid, e2.surface
                    FROM text_annotations_mapped e1 
                    INNER JOIN text_annotations e2 on e1.sentence_aid = e2.sentence_aid
                    WHERE e1.text = ? and e1.path = ? and e2.type = 'sentence'
                )
SELECT 
a1.text as text,
a2.surface as sentence,
name as value,
json_extract(metadata, '$.A0_TEXT')::VARCHAR[] as A0,
json_extract(metadata, '$.A1_TEXT')::VARCHAR[] as A1,
metadata->>'TIME_TEXT' as TIME,
metadata->>'LOC_TEXT' as LOC
FROM text_annotations_mapped a1
INNER JOIN entity_sentences a2 on a1.sentence_aid = a2.sentence_aid
WHERE 
EXISTS (
        SELECT
            1
        FROM
            UNNEST(json_extract(metadata, '$.A0_TEXT')::VARCHAR[]) AS t(tag)
        WHERE
            UPPER(t.tag) = ?
    )
or 
EXISTS (
        SELECT
            1
        FROM
            UNNEST(json_extract(metadata, '$.A1_TEXT')::VARCHAR[]) AS t(tag)
        WHERE
            UPPER(t.tag) = ?
    )
or UPPER(metadata->>'TIME_TEXT') = ?
or UPPER(metadata->>'LOC_TEXT') = ?
                   """,
                [
                    request.entity,
                    request.value,
                    request.entity,
                    request.entity,
                    request.entity,
                    request.entity,
                ],
            )
            .df()
            .to_dict(orient="records")
        )
        for record in result:
            if isinstance(record["A0"], np.ndarray):
                record["A0"] = record["A0"].tolist()
            if isinstance(record["A1"], np.ndarray):
                record["A1"] = record["A1"].tolist()

        return result
    except Exception as e:
        print(e)
        traceback.print_exc()
        return JSONResponse(content=str(e), status_code=500)
