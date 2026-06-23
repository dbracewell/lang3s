from dataclasses import dataclass

from lang3s.data.db import get_ontology
from lang3s.data.schemas import Ontology

from .cluster import GlobalEntityCluster
from .person import parse_person_name, strong_person_conflict


@dataclass
class BlockingResult:
    allowed: bool
    reason: str


class CorefBlocker:
    def __init__(self):
        self.ontology = get_ontology()

    def allow(
        self,
        ent: GlobalEntityCluster,
        cand: GlobalEntityCluster,
    ) -> BlockingResult:
        """
        ent: incoming mention/entity
        cand: candidate cluster/entity
        """

        # 1. ontology hard incompatibility
        if not self._ontology_ok(ent, cand):
            return BlockingResult(False, "ontology_incompatible")

        # 2. person name blocking
        if Ontology.is_ontology_type(ent.dominant_type, "Person"):
            res = self._person_block(ent, cand)
            if not res.allowed:
                return res

        # 3. surface-form blocking
        res = self._surface_block(ent, cand)
        if not res.allowed:
            return res

        return BlockingResult(True, "pass")

    def _ontology_ok(
        self,
        ent: GlobalEntityCluster,
        cand: GlobalEntityCluster,
    ) -> bool:
        """
        Hard ontology gate (stricter than compatibility_score)
        """
        if ent.dominant_type != cand.dominant_type:
            # allow parent-child but not cross-root
            return self.ontology.is_compatible(ent.dominant_type, cand.dominant_type)

        return True

    def _person_block(
        self,
        ent: GlobalEntityCluster,
        cand: GlobalEntityCluster,
    ) -> BlockingResult:
        a = parse_person_name(ent.get_longest_mention().normalized_mention)
        b = parse_person_name(cand.get_longest_mention().normalized_mention)

        # strong negative name conflict
        if strong_person_conflict(a, b):
            return BlockingResult(False, "person_name_conflict")

        # only shared token is common surname
        if a.last and b.last and a.last == b.last:
            if a.first and b.first and a.first != b.first:
                return BlockingResult(False, "surname_collision")

        return BlockingResult(True, "person_ok")

    def _surface_block(
        self, ent: GlobalEntityCluster, cand: GlobalEntityCluster
    ) -> BlockingResult:
        """
        General surface heuristics (works across types)
        """

        s1 = ent.get_longest_mention().normalized_mention
        s2 = cand.get_longest_mention().normalized_mention

        # acronym vs non-matching expansion
        if s1.isupper() and len(s1) <= 5:
            if not self._acronym_match(s1, s2):
                return BlockingResult(False, "acronym_mismatch")

        if s2.isupper() and len(s2) <= 5:
            if not self._acronym_match(s2, s1):
                return BlockingResult(False, "acronym_mismatch")

        return BlockingResult(True, "surface_ok")

    def _acronym_match(self, acronym: str, phrase: str) -> bool:
        letters = "".join(w[0] for w in phrase.split() if w)
        return acronym.lower() == letters.lower()
