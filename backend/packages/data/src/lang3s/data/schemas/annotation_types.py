from enum import StrEnum


class AnnotationTypes(StrEnum):
    TOKEN = "token"
    SENTENCE = "sentence"
    ENTITY = "entity"
    PHRASE_CHUNK = "phrase_chunk"
    NOUN_CHUNK = "noun_chunk"
    EVENT = "event"
    SENSE = "sense"
