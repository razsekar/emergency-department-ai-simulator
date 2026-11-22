"""Shared test helpers for the knowledge_base and rag tests."""
import hashlib
import math
import os
import re
from pathlib import Path

import pymupdf
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]


class FakeEmbedder:
    """Deterministic hashed bag-of-words embedder (384-d, L2-normalized). Lexical overlap => similarity."""

    model_name = "fake-hashed-bow"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * 384
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 384] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class ExplodingEmbedder:
    def embed(self, texts):
        raise RuntimeError("embedding backend unavailable")


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for body in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    os.environ["ALEMBIC_DATABASE_URL"] = url
    return cfg


def create_database(suffix: str) -> tuple[str, callable]:
    base = make_url(os.environ["DATABASE_URL"])
    name = f"edsim_{suffix}_{os.getpid()}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))

    def drop() -> None:
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()

    return base.set(database=name).render_as_string(hide_password=False), drop


def app_db_fixture_body(suffix: str):
    """Generator body for an `app_db` fixture: isolated DB migrated to the RAG branch, app pointed at it."""
    from app.platform import config as platform_config
    from app.platform import db as platform_db
    from app.platform import events as platform_events

    url, drop = create_database(suffix)
    command.upgrade(alembic_config(url), "rag@head")

    mp = pytest.MonkeyPatch()
    mp.setenv("DATABASE_URL", url)
    mp.setattr(platform_events, "_bus", platform_events.EventBus())  # isolate from other modules' subscribers
    platform_config.get_settings.cache_clear()
    platform_db.get_engine.cache_clear()
    platform_db._session_factory.cache_clear()
    try:
        yield url
    finally:
        platform_db.get_engine().dispose()
        mp.undo()
        platform_config.get_settings.cache_clear()
        platform_db.get_engine.cache_clear()
        platform_db._session_factory.cache_clear()
        drop()


def truncate_all(url: str) -> None:
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("TRUNCATE rag.document_chunks, knowledge_base.knowledge_documents"))
    eng.dispose()
