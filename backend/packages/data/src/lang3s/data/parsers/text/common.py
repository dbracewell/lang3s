import html
import re
import unicodedata

_quote_mapping = {
    "“": '"',  # Left double quotation mark
    "”": '"',  # Right double quotation mark
    "‘": "'",  # Left single quotation mark
    "’": "'",  # Right single quotation mark
    "„": '"',  # Double low-9 quotation mark (used in some languages)
    "‚": "'",  # Single low-9 quotation mark
    "«": '"',  # Left-pointing double angle quotation mark
    "»": '"',  # Right-pointing double angle quotation mark
    "‹": "'",  # Single left-pointing angle quotation mark
    "›": "'",  # Single right-pointing angle quotation mark
}

_zero_width_pattern = re.compile(r"[\u200b\u200c\u200d]+")


def normalize_text(text: str) -> str:
    """
    Normalizes text by un-escaping html characters, normalizing unicode, and replacing
    unneeded space.
    """
    text = html.unescape(text)
    text = _zero_width_pattern.sub("", text)
    text = unicodedata.normalize("NFC", text)
    normalized_text = ""
    for char in text:
        normalized_text += _quote_mapping.get(char, char)
    return " ".join(normalized_text.split())
