from dataclasses import dataclass
from typing import Callable, Optional

from lang3s.nlp.language.en import TITLES

from .person import ParsedName, parse_person_name


@dataclass
class AliasEvidence:
    a: str
    b: str
    rule: str
    confidence: float


class AliasMiner:
    def __init__(self, nickname_map=None):
        self.nickname_map: dict[str, str] = nickname_map or {}

    # --- public ---
    def detect(
        self,
        a: str,
        b: str,
        parsed_a: ParsedName | None = None,
        parsed_b: ParsedName | None = None,
    ):
        """
        a, b = entity objects OR surface strings
        parsed_* optional precomputed ParsedName
        """

        parsed_a: ParsedName = parsed_a or parse_person_name(a)
        parsed_b: ParsedName = parsed_b or parse_person_name(b)

        rules: list[
            Callable[[ParsedName, ParsedName, str, str], Optional[AliasEvidence]]
        ] = [
            self._middle_name_alias,
            self._nickname_alias,
            self._last_name_reference,
            self._quoted_alias,
            self._title_alias,
            self._acronym_alias,
        ]

        for r in rules:
            ev = r(parsed_a, parsed_b, a, b)
            if ev:
                return ev

        return None

    def _middle_name_alias(
        self, a: ParsedName, b: ParsedName, s1: str, s2: str
    ) -> Optional[AliasEvidence]:
        if a.last == b.last and a.first == b.first:
            if a.middle != b.middle:
                return AliasEvidence(s1, s2, "middle_name", 0.95)

    def _nickname_alias(
        self, a: ParsedName, b: ParsedName, s1: str, s2: str
    ) -> Optional[AliasEvidence]:
        if a.last == b.last:
            if a.first and b.first:
                if self.nickname_map.get(a.first) == b.first:
                    return AliasEvidence(s1, s2, "nickname", 0.9)
                if self.nickname_map.get(b.first) == a.first:
                    return AliasEvidence(s1, s2, "nickname", 0.9)

    def _last_name_reference(
        self, a: ParsedName, b: ParsedName, s1: str, s2: str
    ) -> Optional[AliasEvidence]:
        if a.last and b.last and a.last == b.last:
            # one mention is just surname
            if len(a.tokens) == 1 or len(b.tokens) == 1:
                return AliasEvidence(s1, s2, "surname_reference", 0.75)

    def _quoted_alias(
        self, a: ParsedName, b: ParsedName, s1: str, s2: str
    ) -> Optional[AliasEvidence]:
        import re

        nick = re.findall(r'"([^"]+)"', s1)
        if nick and nick[0].lower() in s2.lower():
            return AliasEvidence(s1, s2, "quoted_alias", 0.95)

        nick = re.findall(r'"([^"]+)"', s2)
        if nick and nick[0].lower() in s1.lower():
            return AliasEvidence(s1, s2, "quoted_alias", 0.95)

    def _title_alias(
        self, a: ParsedName, b: ParsedName, s1: str, s2: str
    ) -> Optional[AliasEvidence]:
        s1_low = s1.lower()
        s2_low = s2.lower()

        if any(t in s1_low for t in TITLES) and a.last and a.last in s2_low:
            return AliasEvidence(s1, s2, "title_alias", 0.8)

        if any(t in s2_low for t in TITLES) and b.last and b.last in s1_low:
            return AliasEvidence(s1, s2, "title_alias", 0.8)

    def _acronym_alias(
        self, a: ParsedName, b: ParsedName, s1: str, s2: str
    ) -> Optional[AliasEvidence]:
        if s1.isupper() and len(s1) <= 6:
            letters = "".join(w[0] for w in s2.split() if w)
            if letters.lower() == s1.lower():
                return AliasEvidence(s1, s2, "acronym", 0.9)

        if s2.isupper() and len(s2) <= 6:
            letters = "".join(w[0] for w in s1.split() if w)
            if letters.lower() == s2.lower():
                return AliasEvidence(s1, s2, "acronym", 0.9)
