import pytest

from lang3s.core.exceptions.try_catch import try_catch


def test_try_catch_swallows_exception_and_calls_handler():
    captured: list[str] = []

    with try_catch(on_error=lambda exc: captured.append(str(exc))):
        raise ValueError("boom")

    assert captured == ["boom"]


def test_try_catch_reraises_when_configured():
    with pytest.raises(ValueError, match="boom"):
        with try_catch(raise_exception=True):
            raise ValueError("boom")


def test_try_catch_only_handles_configured_exception_types():
    with pytest.raises(TypeError, match="wrong type"):
        with try_catch(handled_exceptions=ValueError):
            raise TypeError("wrong type")
