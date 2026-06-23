from lang3s.core.io.decoders import base64_decoder
from lang3s.data.parsers.parser import ParseResult
from lang3s.data.parsers.text.common import normalize_text


def parse_plain_text(
    text: str | bytes, encoding: str | None = None
) -> ParseResult[str]:
    if not text:
        return ParseResult(content="")
    text = base64_decoder(text, encoding=encoding, mime_type="text/plain")
    if isinstance(text, bytes):
        raise Exception("Plain Text does not support bytes")
    text = normalize_text(text)
    return ParseResult(content=text)
