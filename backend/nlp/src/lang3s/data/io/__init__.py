import base64


def decode_content(
    content: str | bytes, encoding: str | None, mime_type: str
) -> str | bytes:
    """
    Decodes content either raw (utf-8) or base64 encoded.
    """
    is_base_64 = encoding and encoding.lower() == "base64"
    if is_base_64:
        content = base64.b64decode(content)

    if isinstance(content, bytes) and mime_type.lower().startswith("text"):
        effective_encoding = "utf-8" if is_base_64 else encoding
        try:
            content = content.decode(effective_encoding)
        except UnicodeDecodeError:
            content = content.decode(encoding, "latin1")

    return content
