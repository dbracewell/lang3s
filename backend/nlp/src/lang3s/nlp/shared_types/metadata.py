from enum import StrEnum


class Metadata(StrEnum):
    LANGUAGE = "language"
    MIME_TYPE = "mime-type"
    PATH = "path"
    LEMMA = "lemma"
    GENDER = "gender"
    NUMBER = "number"
    IS_STOPWORD = "is_stopword"
    START_CHAR = "start_char"
    END_CHAR = "end_char"
    HEAD = "head"
    RELATION = "relation"
    WEIGHT = "weight"
    COREF = "coref"
    COREF_TEXT = "coref_text"
    A0 = "A0"
    A0_TEXT = "A0_TEXT"
    A1 = "A1"
    A1_TEXT = "A1_TEXT"
    TIME = "TIME"
    TIME_TEXT = "TIME_TEXT"
    LOC = "LOC"
    LOC_TEXT = "LOC_TEXT"
    SOURCE = "source"


class AnnotationTypes(StrEnum):
    TOKEN = "token"
    SENTENCE = "sentence"
    ENTITY = "entity"
    PHRASE_CHUNK = "phrase_chunk"
    NOUN_CHUNK = "noun_chunk"
    EVENT = "event"
