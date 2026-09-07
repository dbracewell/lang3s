import pytest
from pydantic import ValidationError

from lang3s.data.schemas.common import PaginatedQuery


def test_paginated_query_offset_is_computed_from_cursor_and_limit():
    query = PaginatedQuery(cursor=3, limit=10)
    assert query.offset == 20


def test_paginated_query_generate_page_returns_next_cursor_when_extra_item_present():
    query = PaginatedQuery(cursor=3, limit=5)
    next_cursor, items = query.generate_page(list(range(6)))

    assert next_cursor == 4
    assert items == [0, 1, 2, 3, 4]


def test_paginated_query_generate_page_returns_none_when_page_is_complete():
    query = PaginatedQuery(cursor=2, limit=5)
    next_cursor, items = query.generate_page(list(range(5)))

    assert next_cursor is None
    assert items == [0, 1, 2, 3, 4]


def test_paginated_query_limit_validation():
    with pytest.raises(ValidationError):
        PaginatedQuery(cursor=1, limit=4)
