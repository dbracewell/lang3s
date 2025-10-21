from lingua import Language, LanguageDetectorBuilder

languages = [
    Language.ENGLISH,
    Language.JAPANESE,
    Language.SPANISH,
    Language.GERMAN,
    Language.FRENCH,
    Language.DUTCH,
    Language.CHINESE,
]


def detect_language(text: str) -> str:
    detector = LanguageDetectorBuilder.from_languages(*languages).build()
    lang = detector.detect_language_of(text)
    if lang is None:
        return "en"
    return str(lang.iso_code_639_1.name).lower()
