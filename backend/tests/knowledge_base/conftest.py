import pytest

from tests.rag.support import app_db_fixture_body, truncate_all


@pytest.fixture(scope="module")
def app_db():
    yield from app_db_fixture_body("kb")


@pytest.fixture(autouse=True)
def _clean_tables(request):
    if "app_db" in request.fixturenames:
        truncate_all(request.getfixturevalue("app_db"))
    yield
