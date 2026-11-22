"""Idempotent seeding of reference data and demo users.

Run:  python -m app.modules.identity.application.seed
Passwords come from DEMO_ADMIN_PASSWORD / DEMO_PRESENTER_PASSWORD / DEMO_VIEWER_PASSWORD.
Existing users are left unchanged. Passwords are never printed.
"""
from sqlalchemy.orm import Session

from app.modules.identity.domain.passwords import hash_password
from app.modules.identity.domain.permissions import DEMO_USERS, ROLE_PERMISSIONS
from app.modules.identity.infrastructure.repository import IdentityRepository
from app.modules.identity.infrastructure.settings import IdentitySettings
from app.platform import db as platform_db


def seed_demo_users(session: Session, settings: IdentitySettings | None = None) -> dict[str, str]:
    """Returns {username: 'created' | 'exists' | 'skipped (no password configured)'}."""
    settings = settings or IdentitySettings()
    passwords = {
        "demo_admin": settings.demo_admin_password,
        "demo_presenter": settings.demo_presenter_password,
        "demo_viewer": settings.demo_viewer_password,
    }
    repo = IdentityRepository(session)
    repo.ensure_reference_data({r: {str(p) for p in perms} for r, perms in ROLE_PERMISSIONS.items()})
    result: dict[str, str] = {}
    for username, (role, display_name) in DEMO_USERS.items():
        if repo.find_user_by_username(username) is not None:
            result[username] = "exists"
            continue
        password = passwords[username]
        if not password:
            result[username] = "skipped (no password configured)"
            continue
        user = repo.create_user(username, display_name, hash_password(password))
        repo.assign_role(user.id, role)
        result[username] = "created"
    return result


def main() -> None:
    with platform_db.unit_of_work() as session:
        for username, status in seed_demo_users(session).items():
            print(f"{username}: {status}")


if __name__ == "__main__":
    main()
