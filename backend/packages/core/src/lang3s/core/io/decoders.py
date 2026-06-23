import base64

DEFAULT_ENCODING = "utf-8"


def base64_decoder(
    content: str | bytes,
    encoding: str | None,
    mime_type: str,
) -> str | bytes:
    """
    Decodes content either raw (utf-8) or base64 encoded.
    """
    is_base_64: bool = encoding is not None and encoding.lower() == "base64"
    if is_base_64:
        content = base64.b64decode(content)

    if isinstance(content, bytes) and mime_type.lower().startswith("text"):
        effective_encoding = DEFAULT_ENCODING
        if not is_base_64 and encoding:
            effective_encoding = encoding
        try:
            return content.decode(effective_encoding)
        except UnicodeDecodeError:
            return content.decode(effective_encoding, "latin1")

    return content
