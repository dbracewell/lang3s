from lang3s.data.io import decode_content
from lang3s.data.parsers.parser import ParseResult
from lang3s.data.parsers.text.common import normalize_text


def parse_html(text: str | bytes, encoding: str | None = None) -> ParseResult[str]:
    from bs4 import BeautifulSoup

    if not text:
        return ParseResult(content="")

    html = decode_content(text, encoding=encoding, mime_type="text/html")
    soup = BeautifulSoup(
        html,
        "html.parser",
    )
    text = normalize_text(soup.get_text())
    urls = [a.get("href") for a in soup.find_all("a") if a.get("href") is not None]
    title = soup.title.string if soup.title is not None else None

    metadata = dict()
    if urls:
        metadata["urls"] = urls
    if title:
        metadata["title"] = title

    for meta in soup.find_all("meta"):
        name = meta.get("name", meta.get("property", ""))
        content = meta.get("content", "")
        if name and content:
            metadata[name] = content

    return ParseResult(content=text, metadata=metadata)
