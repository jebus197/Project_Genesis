"""Web test fixtures — app factory and HTTP client."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from genesis.web.app import create_app
from genesis.web.deps import get_resolver, get_service


@pytest.fixture(scope="module")
def app():
    """Create the FastAPI app once per test module.

    Clears the DI singletons first so each module gets a fresh service.
    """
    get_resolver.cache_clear()
    get_service.cache_clear()
    application = create_app()
    yield application
    get_resolver.cache_clear()
    get_service.cache_clear()


@pytest.fixture()
async def client(app):
    """Async HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
