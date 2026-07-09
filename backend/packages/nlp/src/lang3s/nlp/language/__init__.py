from __future__ import annotations

from typing import TYPE_CHECKING, cast

from spacy.tokens import Span, Token

if TYPE_CHECKING:
    from lang3s.data.schemas import TextAnnotation


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
    if isinstance(word, Span) or isinstance(word, Token):
        language = language or word.doc.lang_
        PERSON_PRONOUNS = get_personal_pronouns(language)
        return len(word) == 1 and (
            word[0].tag_ == "PRP" or word.text.lower() in PERSON_PRONOUNS
        )
    elif isinstance(word, str):
        PERSON_PRONOUNS = get_personal_pronouns(language or "en")
        return word.lower() in PERSON_PRONOUNS

    language = language or word.document.language or "en"  # type:ignore
    PERSON_PRONOUNS = get_personal_pronouns(language)
    tokens: list[TextAnnotation] = word.tokens  # type:ignore
    return len(tokens) == 1 and (tokens[0].content.lower() in PERSON_PRONOUNS)
