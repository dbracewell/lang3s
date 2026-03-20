from __future__ import annotations

from typing import TYPE_CHECKING

from spacy.tokens import Span, Token

from lang3s.nlp.metadata import Metadata

if TYPE_CHECKING:
    from lang3s.nlp.shared_types import TextAnnotation


def uses_whitespace(language: str) -> bool:
    language = language.lower()
    if language in ("zh", "ja"):
        return False
    return True


def get_common_person_titles(language: str) -> set[str]:
    language = language.lower()
    if language == "en":
        from .en import TITLES

        return TITLES
    return set()


def get_acronym_expansions(language: str) -> dict[str, str]:
    language = language.lower()
    if language == "en":
        from .en import ACRONYM_EXPANSIONS

        return ACRONYM_EXPANSIONS
    return {}


def get_personal_pronouns(language: str) -> set[str]:
    language = language.lower()
    if language == "en":
        from .en import PERSON_PRONOUNS

        return PERSON_PRONOUNS
    return set()


def is_person_pronoun(
    word: Token | Span | str | TextAnnotation,
    language: str | None = None,
) -> bool:
    if language is None:
        if isinstance(word, Span) or isinstance(word, Token):
            language = word.doc.lang_
        else:
            language = word.owner.get(Metadata.LANGUAGE, "en")
    PERSON_PRONOUNS = get_personal_pronouns(language)

    if isinstance(word, str):
        return word.lower() in PERSON_PRONOUNS

    if isinstance(word, Span):
        return len(word) == 1 and (
            word[0].tag_ == "PRP" or word.text.lower() in PERSON_PRONOUNS
        )

    return len(word.tokens) == 1 and (word.tokens[0].text.lower() in PERSON_PRONOUNS)
