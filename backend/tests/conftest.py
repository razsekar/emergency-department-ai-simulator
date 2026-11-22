import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def test_db_url():
    """Create an isolated empty database for migration tests; remove it afterwards."""
    base = make_url(os.environ["DATABASE_URL"])
    name = f"edsim_test_{os.getpid()}"  # unique per pytest process so parallel runs don't collide
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))
    yield base.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()
