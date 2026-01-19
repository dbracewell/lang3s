from url_normalize import url_normalize


def normalize_url(url_string) -> str:
    """
    Normalizes a given URL string using the url-normalize library.

    Args:
        url_string: The URL string to normalize.

    Returns:
        The normalized URL string, or None if the input is not a valid URL.
    """
    try:
        normalized = url_normalize(url_string)
        return normalized
    except Exception as e:
        print(f"Error normalizing URL: {e}")
    return url_string
