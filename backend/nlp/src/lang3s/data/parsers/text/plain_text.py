import re

from lang3s.data.io import decode_content
from lang3s.data.parsers.parser import Parser, ParseResult
from lang3s.data.parsers.text.common import normalize_text

_clean_malformed_html_for_markdown = re.compile(r"</(?=\d)")


class PlainTextParser(Parser[ParseResult[str]]):
    def parse(self, text: str | bytes, encoding: str | None = None) -> ParseResult[str]:
        if not text:
            return ParseResult(content="")
        text = decode_content(text, encoding=encoding, mime_type="text/markdown")
        text = normalize_text(text)
        return ParseResult(content=text)
