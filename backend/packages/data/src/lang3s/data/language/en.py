from .core import Language, register_language


@register_language("en")
class ENLanguage(Language):
    pass
