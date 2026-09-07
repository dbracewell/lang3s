from __future__ import annotations

from collections import defaultdict
from typing import Dict

import numpy as np
from lang3s.nlp.coref.alias import AliasMiner
from lang3s.nlp.coref.blocking import CorefBlocker
from lang3s.nlp.coref.cluster import GlobalEntityCluster
from lang3s.nlp.coref.helper import should_perform_coref
from lang3s.nlp.shared_types import Document, TextAnnotation
from lang3s.ontology import ontology
from lang3s.ontology.core import is_ontology_type
from lang3s.utils.maths import normalize
from rapidfuzz import fuzz

from lang3s.nlp.language import is_person_pronoun


class StreamingEntityResolver:
    def __init__(self, threshold=0.85):
        self.threshold = threshold
        self.clusters: Dict[str, GlobalEntityCluster] = {}
        self.blocker = CorefBlocker()
        self.alias_miner = AliasMiner()

    def _hybrid_score(
        self,
        candidate: GlobalEntityCluster,
        target: GlobalEntityCluster,
    ) -> float:
        """
        The Core Logic: Combines Dense Vector Similarity + String Match + Ontology
        """
        sem_sim = float(np.dot(candidate.embedding_centroid, target.embedding_centroid))
        str_sim = 0
        for mention in target.mentions:
            str_sim = max(
                str_sim,
                max(
                    fuzz.ratio(candidate.normalized_mention, mention.normalized_mention)
                    for candidate in candidate.mentions
                ),
            )
        str_sim /= 100

        type_sim = ontology.compatibility_score(
            candidate.dominant_type, target.dominant_type
        )

        # Filter: If types are fundamentally incompatible, force score to 0
        if type_sim == 0.0:
            return 0.0

        bonus = 0.3 if str_sim >= 1.0 and type_sim >= 1.0 else 0.0
        # Weighted combination
        # Embeddings provide recall, String provides precision
        final_score = (0.5 * sem_sim) + (0.3 * str_sim) + (0.32 * type_sim) + bonus

        return final_score

    def process_document_mentions(self, document: Document):
        in_doc_coref: dict[str, list[TextAnnotation]] = defaultdict(list)
        for mention in document.text.annotations:
            if (
                not should_perform_coref(mention)
                or is_person_pronoun(mention.text)
                or mention.text.lower() in ("it", "its")
            ):
                continue
            in_doc_coref[mention.coref.id].append(mention)

        for i, (mention_id, mentions) in enumerate(in_doc_coref.items()):
            if mention_id not in [m.id for m in mentions]:
                continue

            temp_cluster = GlobalEntityCluster(
                cluster_id=mention_id,
                embedding_centroid=normalize(
                    np.mean([m.embedding for m in mentions], axis=0)
                ),
            )

            for mention in mentions:
                temp_cluster.add_mention(mention)

            best_cluster_id = None
            best_score = -1.0

            for c_id, candidate in self.clusters.items():
                block = self.blocker.allow(
                    temp_cluster,
                    candidate,
                )
                if is_ontology_type(
                    temp_cluster.dominant_type, "Person"
                ) and is_ontology_type(candidate.dominant_type, "Person"):
                    print(
                        temp_cluster.get_longest_mention().mention,
                        candidate.get_longest_mention().mention,
                        block,
                    )
                if not block.allowed:
                    continue

                incoming = temp_cluster.get_longest_mention().normalized_mention

                # 2. compute propagation boost
                prop = candidate.alias_graph.propagate(incoming)

                alias_boost = max(
                    (prop.get(m.normalized_mention, 0.0) for m in candidate.mentions),
                    default=0.0,
                )

                # 3. compute hybrid score
                score = self._hybrid_score(candidate, temp_cluster) + alias_boost * 0.25

                if score > best_score:
                    best_score = score
                    best_cluster_id = c_id

            if best_score > self.threshold and best_cluster_id:
                self.clusters[best_cluster_id].merge(temp_cluster)
            else:
                new_id = f"ENT_{len(self.clusters)}"
                temp_cluster.cluster_id = new_id
                self.clusters[new_id] = temp_cluster


# import lang3s.data.db.text_database as text_db
#
# resolver = StreamingEntityResolver()
# processed = 0
# for doc in text_db.get_documents(limit=100):
#     resolver.process_document_mentions(doc)
#     processed += 1
#     if processed >= 1000:
#         break
#
# with open("/Users/ik/prj/Lang3s/coref.txt", "w") as f:
#     for id, cluster in resolver.clusters.items():
#         if cluster.count > 2:
#             f.write(f"{cluster.dominant_type} ({cluster.count}) \n")
#             f.write(" | ".join([x.mention for x in cluster.mentions]) + "\n\n")
