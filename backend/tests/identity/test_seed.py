from sqlalchemy import text

from app.modules.identity.application.seed import seed_demo_users
from app.modules.identity.infrastructure.settings import IdentitySettings
from tests.identity.conftest import PASSWORDS


def test_seed_is_idempotent_and_stores_only_hashes(db, ident_engine):
    with db() as session:
        assert set(seed_demo_users(session).values()) == {"exists"}  # already seeded by fixture
    with ident_engine.connect() as c:
        hashes = [r[0] for r in c.execute(text("SELECT password_hash FROM identity.users"))]
    assert len(hashes) == 3
    for h in hashes:
        assert h.startswith("scrypt$") and not any(p in h for p in PASSWORDS.values())


def test_seed_skips_users_without_configured_password(db, ident_engine):
    with ident_engine.begin() as c:
        c.execute(text("TRUNCATE identity.user_roles, identity.users CASCADE"))
    settings = IdentitySettings(demo_admin_password="", demo_presenter_password="p" * 10,
                                demo_viewer_password="")
    with db() as session:
        result = seed_demo_users(session, settings)
    assert result["demo_presenter"] == "created"
    assert result["demo_admin"].startswith("skipped") and result["demo_viewer"].startswith("skipped")
