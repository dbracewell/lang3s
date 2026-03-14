import math
from collections import defaultdict

import networkx as nx
import numpy as np

from lang3s.data.db.analytics_db import AnalyticsDB, get_analytics_db
from lang3s.services.model.analytics_models import *
from lang3s.utils.maths import remap


def truncate(text: str, max_length: int = 35) -> str:
    if len(text) < max_length:
        return text
    truncated = text[: text.rindex(" ", 1, max_length)].strip()
    if truncated:
        return f"{truncated}..."
    return f"{truncated[:max_length].strip()}..."


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


class AnalyticsService:
    def __init__(self, db: AnalyticsDB):
        self.db: AnalyticsDB = db
        self.queries = QueryTemplateEngine()

    def get_annotation_counts(self, request: AnnotationCountsRequest):
        params: list[Any] = self.queries.prepare_path_params(request.mappings)
        total_query = self.queries.render(
            "analytics/annotation_total_unique_filtered.sql.j2",
            mapping_list=request.mappings,
        )
        total = self.db.execute(total_query, params).fetchone()[0]

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
                request.page_size,
            ]
        )
        result = self.db.run_query(
            "analytics/annotation_count_by_text_name.sql.j2",
            parameters=params,
            mapping_list=request.mappings,
            order_by_col=request.order_by,
            filter=request.filter,
        )
        total_pages = math.ceil(total / request.page_size)
        return {
            "total": total,
            "totalPages": math.ceil(total / request.page_size),
            "results": result,
            "nextPage": request.page + 1 if request.page + 1 <= total_pages else None,
            "prevPage": request.page - 1 if request.page > 1 else None,
        }

    def get_annotation_co_occurrences(self, request: AnnotationCoOccurrenceRequest):
        params = [request.value, request.entity]
        params.extend(self.queries.prepare_path_params(request.targets))
        result = self.db.run_query(
            "analytics/annotation_co_occurrence.sql.j2",
            parameters=params,
            mapping_list=request.targets,
        )
        return result

    def _calculate_norm_score(
        self, group: list[dict[str, Any]], low_value_index: int, high_value_index: int
    ) -> list[dict[str, Any]]:
        min_value = group[low_value_index]["rawScore"] if group else 0
        max_value = group[high_value_index]["rawScore"] if group else 0
        for x in group:
            x.update({"normScore": remap(x["rawScore"], min_value, max_value, 0, 1)})
        return group

    def get_annotation_affinity_metrics(self, request: AnnotationMetricRequest):
        params = self.queries.prepare_path_params(request.values)
        data = self.db.run_query(
            "analytics/annotation_affinity_metric.sql.j2",
            parameters=params,
            mapping_list=request.values,
        )
        low_group = [x for x in data if x["category"] == "low"]
        high_group = [x for x in data if x["category"] == "high"]
        low_group = self._calculate_norm_score(low_group, -1, 0)
        high_group = self._calculate_norm_score(high_group, -1, 0)
        high_group.reverse()
        return low_group + high_group

    def get_annotation_topic_score_metrics(self, request: AnnotationMetricRequest):
        params = self.queries.prepare_path_params(request.values)
        data = self.db.run_query(
            "analytics/annotation_topic_metric.sql.j2",
            parameters=params,
            mapping_list=request.values,
        )
        low_group = [x for x in data if x["category"] == "low"]
        high_group = [x for x in data if x["category"] == "high"]
        low_group = self._calculate_norm_score(low_group, -1, 0)
        high_group = self._calculate_norm_score(high_group, -1, 0)
        high_group.reverse()
        return low_group + high_group

    def get_annotation_events(self, request: AnnotationEventRequest):
        result = self.db.run_query(
            "analytics/annotation_events.sql.j2",
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

    def get_annotation_cohorts(self):
        edges = self.db.run_query("analytics/annotation_cohorts.sql.j2")
        seen = set()
        nodes = []
        for x in edges:
            for id, name, support in [
                (x["id1"], x["source"], x["source_document_count"]),
                (x["id2"], x["target"], x["target_document_count"]),
            ]:
                if id not in seen:
                    seen.add(id)
                    nodes.append(
                        {
                            "id": id,
                            "text": name,
                            "display": truncate(name),
                            "value": support,
                            "r": 20,
                        }
                    )
        clusters, id_cid = cluster_points(edges)
        for node in nodes:
            node["cid"] = id_cid.get(node["id"], None)
        return {"edges": edges, "nodes": nodes, "clusters": clusters, "id_cid": id_cid}

    def get_annotation_cohort_information(
        self, request: AnnotationCohortInformationRequest
    ):
        edges = self.db.run_query(
            "analytics/annotation_cohort_information.sql.j2",
            parameters=request.ids + request.ids,
            cohort=request.ids,
        )
        grouped = defaultdict(list)
        for e in edges:
            s1_id = e["sourceId"]
            s2_id = e["targetId"]
            grouped[s2_id].append(s1_id)
            grouped[s1_id].append(s2_id)

        ranked = [
            {"id": entity_id, "value": len(neighbors)}
            for entity_id, neighbors in grouped.items()
        ]
        ranked.sort(key=lambda x: x["value"], reverse=True)

        return {"edges": edges, "ranked": ranked}

    def get_ranked_entities_for_topic(self, id: str):
        params = [id, 5000]
        params.extend(
            self.queries.prepare_path_params(
                ["ALL.Entity.Physical", "ALL.Entity.Abstract.Social_And_Collective"]
            )
        )
        result = self.db.run_query(
            "analytics/topic_ranked_annotations.sql.j2",
            parameters=params,
            mapping_list=[
                "ALL.Entity.Physical",
                "ALL.Entity.Abstract.Social_And_Collective",
            ],
        )
        return result

    def build_annotation_stats(self):
        self.db.build_annotation_stats()

    def finish_data_ingestion(self):
        self.db.execute(
            "PRAGMA create_fts_index('text_annotations', 'id', 'text', overwrite=1);"
        )
        self.build_annotation_stats()
        self.db.commit()

    def ingest_annotation_batch_from_file(self, temp_file: str) -> None:
        self.db.execute(
            f"INSERT OR IGNORE INTO text_annotations SELECT * FROM read_json_auto('{temp_file}', union_by_name=true, sample_size=-1);"
        )
        self.db.commit()

    def shutdown(self) -> None:
        self.db.close()


analytics_service: AnalyticsService = None  # type:ignore


def init_analytics_service() -> None:
    global analytics_service
    if analytics_service is None:
        analytics_service = AnalyticsService(get_analytics_db())


def get_analytics_service() -> AnalyticsService:
    global analytics_service
    if analytics_service is None:
        init_analytics_service()
    return analytics_service


def shutdown_analytics_service() -> None:
    global analytics_service
    if analytics_service is not None:
        analytics_service.shutdown()
    analytics_service = None
