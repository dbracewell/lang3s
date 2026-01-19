import re

import markdown
from bs4 import BeautifulSoup

from lang3s.data.io import decode_content
from lang3s.data.parsers.parser import Parser, ParseResult
from lang3s.data.parsers.text.common import normalize_text


class MarkDownParser(Parser[ParseResult[str]]):
    _url_regex = re.compile(r"http\S+")
    _clean_malformed_html_for_markdown = re.compile(r"</(?=\d)")

    def parse(self, text: str | bytes, encoding: str | None = None) -> ParseResult[str]:
        if not text:
            return ParseResult(content="")

        text = decode_content(text, encoding=encoding, mime_type="text/markdown")
        cleaned = MarkDownParser._clean_malformed_html_for_markdown.sub("", text)
        try:
            html = markdown.markdown(cleaned, extensions=["extra"])
        except Exception:
            html = cleaned

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()

        urls = []
        for url in MarkDownParser._url_regex.findall(text):
            urls.append(url)
        metadata = {}
        if urls:
            metadata["urls"] = urls

        text = MarkDownParser._url_regex.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = normalize_text(text)
        return ParseResult(metadata=metadata, content=text)
