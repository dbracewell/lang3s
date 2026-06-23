import re

import markdown
from bs4 import BeautifulSoup

from lang3s.core.io.decoders import base64_decoder
from lang3s.data.parsers.parser import ParseResult
from lang3s.data.parsers.text.common import normalize_text

_url_regex = re.compile(r"http\S+")
_clean_malformed_html_for_markdown = re.compile(r"</(?=\d)")


def parse_markdown(text: str | bytes, encoding: str | None = None) -> ParseResult[str]:
    if not text:
        return ParseResult(content="")

    text = base64_decoder(text, encoding=encoding, mime_type="text/markdown")
    if isinstance(text, bytes):
        raise Exception("Markdown parser does not support bytes")

    cleaned = _clean_malformed_html_for_markdown.sub("", text)
    try:
        html = markdown.markdown(cleaned, extensions=["extra"])
    except UnicodeDecodeError | ValueError:
        html = cleaned

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    urls = []
    for url in _url_regex.findall(text):
        urls.append(url)
    metadata = {}
    if urls:
        metadata["urls"] = urls

    text = _url_regex.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = normalize_text(text)
    return ParseResult(metadata=metadata, content=text)
