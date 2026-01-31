import asyncio
import math
from collections import defaultdict
from contextlib import asynccontextmanager

import networkx as nx
import numpy as np
from fastapi import APIRouter, Depends, FastAPI

from lang3s.data.db import analytics
from lang3s.services.model.analytics import *
from lang3s.services.service_logging import get_logger
from lang3s.services.worker.analytics_worker import analytics_worker
from lang3s.utils.maths import remap

logger = get_logger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

BATCH_TIMEOUT = 30

background_tasks = set()


@asynccontextmanager
async def analytics_lifecycle(app: FastAPI):
    logger.info("Initializing DuckDB...")
    analytics.init_db()
    worker_task = asyncio.create_task(asyncio.to_thread(analytics_worker, app.state))
    background_tasks.add(worker_task)
    worker_task.add_done_callback(background_tasks.discard)
    yield

    app.should_exit = True
    try:
        await asyncio.wait_for(worker_task, timeout=5.0)
        logger.info("✅ Worker finished gracefully.")
    except asyncio.TimeoutError:
        pass

    logger.info("Closing DuckDB...")
    analytics.analytics_db.close()


@router.get("/topic/{id}")
async def get_topic(id: str, db=Depends(analytics.get_db)):
    params = [id, 5000]
    params.extend(
        db.prepare_path_params(
            ["ALL.Entity.Physical", "ALL.Entity.Abstract.Social_And_Collective"]
        )
    )
    result = db.run_query(
        "topic_information.sql.j2",
        parameters=params,
        mapping_list=[
            "ALL.Entity.Physical",
            "ALL.Entity.Abstract.Social_And_Collective",
        ],
    )
    return result


@router.post("/cohortinformation")
async def cohort_information(
    request: CohortInformationRequest, db=Depends(analytics.get_db)
):
    edges = db.run_query(
        "cohort_information.sql.j2",
        parameters=request.ids + request.ids,
        cohort=request.ids,
    )
    grouped = defaultdict(list)
    for e in edges:
        s1_id = e["sourceId"]
        s2_id = e["targetId"]

        # Add bidirectional connections (Undirected Graph logic)
        grouped[s2_id].append(s1_id)
        grouped[s1_id].append(s2_id)

    ranked = [
        {"id": entity_id, "support": len(neighbors)}
        for entity_id, neighbors in grouped.items()
    ]
    ranked.sort(key=lambda x: x["support"], reverse=True)

    return {"edges": edges, "ranked": ranked}


@router.post("/cohorts")
async def cohorts(db=Depends(analytics.get_db)):
    edges = db.run_query("cohorts.sql.j2")
    seen = set()
    nodes = []
    for x in edges:
        if x["id1"] not in seen:
            seen.add(x["id1"])
            nodes.append(
                {
                    "id": x["id1"],
                    "name": x["source"],
                    "r": 20,
                    "support": x["source_document_count"],
                }
            )
        if x["id2"] not in seen:
            seen.add(x["id2"])
            nodes.append(
                {
                    "id": x["id2"],
                    "name": x["target"],
                    "r": 20,
                    "support": x["target_document_count"],
                }
            )
    clusters, id_cid = cluster_points(edges)
    return {"edges": edges, "nodes": nodes, "clusters": clusters, "id_cid": id_cid}


@router.post("/topicscore")
async def topic_score(request: AffinityRequest, db=Depends(analytics.get_db)):
    params = db.prepare_path_params(request.values)
    data = db.run_query(
        "annotation_topic_score.sql.j2",
        parameters=params,
        mapping_list=request.values,
    )
    low_group = [x for x in data if x["category"] == "low"]
    high_group = [x for x in data if x["category"] == "high"]

    min_low_v = low_group[-1]["rawScore"] if low_group else 0
    max_low_v = low_group[0]["rawScore"] if low_group else 1
    max_high_v = high_group[0]["rawScore"] if high_group else 0
    min_high_v = high_group[-1]["rawScore"] if high_group else 0

    for x in low_group:
        x.update({"normScore": remap(x["rawScore"], min_low_v, max_low_v, 0, 1)})

    for x in high_group:
        x.update({"normScore": remap(x["rawScore"], min_high_v, max_high_v, 0, 1)})

    return low_group + high_group


@router.post("/affinity")
async def loaners(request: AnnotationLonersRequest, db=Depends(analytics.get_db)):
    params = db.prepare_path_params(request.values)
    data = db.run_query(
        "annotation_affinity.sql.j2",
        parameters=params,
        mapping_list=request.values,
    )
    low_group = [x for x in data if x["category"] == "low"]
    high_group = [x for x in data if x["category"] == "high"]

    min_low_v = low_group[-1]["rawScore"] if low_group else 0
    max_low_v = low_group[0]["rawScore"] if low_group else 0
    max_high_v = high_group[0]["rawScore"] if high_group else 0
    min_high_v = high_group[-1]["rawScore"] if high_group else 0

    for x in low_group:
        x.update({"normScore": remap(x["rawScore"], min_low_v, max_low_v, 0, 1)})

    for x in high_group:
        x.update({"normScore": remap(x["rawScore"], min_high_v, max_high_v, 0, 1)})

    return low_group + high_group


@router.post("/counts")
async def counts(request: CountsRequest, db=Depends(analytics.get_db)):
    params = db.prepare_path_params(request.mappings)

    total_query = db.get_template("entity_total_counts.sql.j2").render(
        mapping_list=request.mappings
    )
    total = db.execute(total_query, params).fetchone()[0]

    order_by_col = "COUNT(0)"
    if request.order_by == "mentionsPerDoc":
        order_by_col = "COUNT(0) / COUNT(DISTINCT document_id)"
    elif request.order_by == "docs":
        order_by_col = "count(DISTINCT document_id)"

    request.filter = (
        request.filter
        if request.filter is not None and request.filter.strip() != ""
        else None
    )

    if request.filter:
        params.append(f"{request.filter}%")

    params.extend(
        [
            (request.page - 1) * request.page_size,
            request.page_size + 1,
        ]
    )
    result = db.run_query(
        "entity_counts.sql.j2",
        parameters=params,
        mapping_list=request.mappings,
        order_by_col=order_by_col,
        filter=request.filter,
    )
    hasNextPage = len(result) > request.page_size
    if hasNextPage:
        result = result[:-1]
    return {
        "total": total,
        "totalPages": math.ceil(total / request.page_size),
        "results": result,
        "nextPage": request.page + 1 if hasNextPage else None,
        "prevPage": request.page - 1 if request.page > 1 else None,
    }


@router.post("/cooccurrence")
async def cooccurrence(request: CoOccurrenceRequest, db=Depends(analytics.get_db)):
    params = [request.value, request.entity]
    params.extend(db.prepare_path_params(request.targets))
    result = db.run_query(
        "entity_co_occurrence.sql.j2",
        parameters=params,
        mapping_list=request.targets,
    )
    return result


@router.put("/updatestats")
async def update_stats(db=Depends(analytics.get_db)):
    db.build_annotation_stats()


@router.post("/events")
async def events(request: EventRequest, db=Depends(analytics.get_db)):
    result = db.run_query(
        "entity_events.sql.j2",
        parameters=[
            request.entity,
            request.value,
            request.entity,
            request.entity,
            request.entity,
            request.entity,
        ],
    )
    for record in result:
        if isinstance(record["A0"], np.ndarray):
            record["A0"] = record["A0"].tolist()
        if isinstance(record["A1"], np.ndarray):
            record["A1"] = record["A1"].tolist()

    return result


def cluster_points(similarities):
    # 1. Build a Graph
    G = nx.Graph()

    # Add all edges (similarities)
    # This automatically handles the "filter" step because nodes
    # without edges won't be part of the component unless added explicitly.
    # If you strictly need to filter pointsRaw against similarities first:
    connected_ids = set()
    for s in similarities:
        G.add_edge(s["id1"], s["id2"])
        connected_ids.add(s["id1"])
        connected_ids.add(s["id2"])

    # 2. Find Connected Components (The "Clustering")
    # This replaces the loop of 50
    # Returns a list of sets: [{'id1', 'id2'}, {'id3'}, ...]
    components = list(nx.connected_components(G))

    # 3. Sort by size (largest groups first)
    components.sort(key=len, reverse=True)

    # 4. Format the output
    final_clusters = []
    id_cid = {}
    for comp in components:
        group = []
        comp_id = None
        for p_id in comp:
            if comp_id is None:
                comp_id = p_id
            id_cid[p_id] = comp_id
            parts = p_id.split("-")
            name = "-".join(parts[:-1])
            p_type = parts[-1]

            group.append({"id": p_id, "name": name, "type": p_type})
        final_clusters.append(group)

    return final_clusters, id_cid
