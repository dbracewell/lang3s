from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Set

import numpy as np

from lang3s.nlp.coref.alias import AliasMiner
from lang3s.ontology import ontology

if TYPE_CHECKING:
    from lang3s.nlp.shared_types import TextAnnotation


@dataclass
class Mention:
    mention: str
    normalized_mention: str
    mention_type: str
    mention_id: str

    def __hash__(self):
        return hash(self.mention_id)


@dataclass
class AliasEdge:
    src: str
    dst: str
    weight: float
    rule: str


class AliasGraph:
    def __init__(self, decay=0.85, min_conf=0.5):
        self.adj: dict[str, list[AliasEdge]] = defaultdict(list)
        self.decay = decay
        self.min_conf = min_conf

    def add_edge(self, a: str, b: str, weight: float, rule: str):
        self.adj[a].append(AliasEdge(a, b, weight, rule))
        self.adj[b].append(AliasEdge(b, a, weight, rule))

    def propagate(self, start):
        """
        Returns: dict[target_surface] = propagated_confidence
        """

        scores = {start: 1.0}
        queue = [(0, start)]

        while queue:
            depth, node = queue.pop(0)
            if depth > 3:
                continue

            for edge in self.adj[node]:
                new_score = scores[node] * edge.weight * self.decay

                if new_score < self.min_conf:
                    continue

                if edge.dst not in scores or new_score > scores[edge.dst]:
                    scores[edge.dst] = new_score
                    queue.append((depth + 1, edge.dst))

        return scores


@dataclass
class GlobalEntityCluster:
    cluster_id: str
    embedding_centroid: np.ndarray
    mentions: Set[Mention] = field(default_factory=set)
    entity_types: Counter = field(default_factory=Counter)
    alias_graph: AliasGraph = field(default_factory=AliasGraph)
    count: int = 0

    def merge(self, other: GlobalEntityCluster):
        """Online update of the cluster center and features."""
        # Moving average for centroid (simple version)
        alpha = 1.0 / self.count
        self.embedding_centroid = (1 - alpha) * self.embedding_centroid + (
            alpha * other.embedding_centroid
        )
        self.mentions |= other.mentions
        self.entity_types.update(other.entity_types)
        self.count += other.count
        incoming = other.get_longest_mention().normalized_mention
        alias_miner = AliasMiner()
        for m in other.mentions:
            alias = alias_miner.detect(incoming, m.normalized_mention)
            if alias:
                self.alias_graph.add_edge(
                    alias.a, alias.b, alias.confidence, alias.rule
                )

    def add_alias(self, a: str, b: str, confidence: float, rule: str):
        self.alias_graph.add_edge(a, b, confidence, rule)

    def add_mention(self, mention: TextAnnotation) -> None:
        cleaned_mention = re.sub(r"'[a-z]$", "", mention.text)
        cleaned_mention = re.sub(r"[^\w\s]", " ", cleaned_mention)
        cleaned_mention = re.sub(r"\s+", " ", cleaned_mention).lower().strip()
        entity_type = ontology.get_ontology_concept_for_mapping(mention.mapping)
        self.mentions.add(
            Mention(
                mention=mention.text,
                normalized_mention=cleaned_mention,
                mention_type=entity_type,
                mention_id=mention.id,
            )
        )
        self.entity_types[entity_type] += 1
        self.count += 1

    def get_longest_mention(self):
        return sorted(self.mentions, key=lambda x: len(x.normalized_mention))[-1]

    def canonical_name(self):
        scores = {}

        for node, edges in self.alias_graph.adj.items():
            if not edges:
                continue
            scores[node] = sum(e.weight for e in edges) / len(edges)

        return max(scores, key=scores.get)

    @property
    def dominant_type(self) -> str:
        return self.entity_types.most_common(1)[0][0]
