from lang3s.data.io import decode_content
from lang3s.data.parsers.parser import ParseResult
from lang3s.data.parsers.text.common import normalize_text


def parse_plain_text(
    text: str | bytes, encoding: str | None = None
) -> ParseResult[str]:
    if not text:
        return ParseResult(content="")
    text = decode_content(text, encoding=encoding, mime_type="text/plain")
    text = normalize_text(text)
    return ParseResult(content=text)
