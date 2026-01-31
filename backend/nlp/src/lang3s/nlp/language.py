from spacy.tokens import Span, Token

from lang3s.nlp.shared_types import TextAnnotation

PERSON_PRONOUNS = [
    # personal
    "i",
    "me",
    "we",
    "us",
    "you",
    "he",
    "him",
    "she",
    "her",
    "they",
    "them",
    # possessive
    "my",
    "mine",
    "our",
    "ours",
    "your",
    "yours",
    "his",
    "her",
    "hers",
    "their",
    "theirs",
    # reflexive / intensive
    "myself",
    "yourself",
    "himself",
    "herself",
    "itself",
    "ourselves",
    "yourselves",
    "themselves",
    "themself",
    # indefinite (human-related)
    "anyone",
    "anybody",
    "everyone",
    "everybody",
    "someone",
    "somebody",
    "noone",
    "nobody",
    "each",
    "either",
    "neither",
    # relative / interrogative
    "who",
    "whom",
    "whose",
]


def is_person_pronoun(
    word: Token | Span | str | TextAnnotation,
) -> bool:
    if isinstance(word, str):
        return word.lower() in PERSON_PRONOUNS

    if isinstance(word, TextAnnotation):
        return len(word.tokens) == 1 and (
            word.tokens[0].text.lower() in PERSON_PRONOUNS
        )

    return len(word) == 1 and (
        word[0].tag_ == "PRP" or word.text.lower() in PERSON_PRONOUNS
    )
