import pytest
from sqlalchemy import text

from app.modules.identity.domain.permissions import DEMO_USERS, ROLE_PERMISSIONS, Permission
from tests.identity.conftest import auth_headers

ROLE_OF = {user: role for user, (role, _) in DEMO_USERS.items()}


@pytest.fixture
def tokens(client):
    return {user: auth_headers(client, user) for user in ROLE_OF}


def test_permission_matrix_enforced_for_every_role_and_permission(client, tokens):
    mismatches = []
    for user, role in ROLE_OF.items():
        for perm in Permission:
            r = client.get("/_perm/" + perm.value.replace(":", "-"), headers=tokens[user])
            expected = 200 if perm in ROLE_PERMISSIONS[role] else 403
            if r.status_code != expected:
                mismatches.append((role, perm.value, r.status_code, expected))
    assert not mismatches


def test_missing_token_is_401_on_every_protected_route(client):
    for perm in Permission:
        assert client.get("/_perm/" + perm.value.replace(":", "-")).status_code == 401


def test_forbidden_uses_standard_error_shape(client, tokens):
    r = client.get("/_perm/audit-read", headers=tokens["demo_viewer"])
    assert r.status_code == 403
    assert r.json() == {"error": {"code": "forbidden", "message": "Insufficient permissions"}}


def test_viewer_cannot_mutate_but_presenter_can(client, tokens):
    assert client.get("/_perm/scenario-apply", headers=tokens["demo_viewer"]).status_code == 403
    assert client.get("/_perm/scenario-apply", headers=tokens["demo_presenter"]).status_code == 200
    assert client.get("/_perm/models-configure", headers=tokens["demo_presenter"]).status_code == 403


def test_database_reference_data_matches_domain_matrix(client, ident_engine):
    with ident_engine.connect() as c:
        rows = c.execute(text(
            "SELECT r.name, p.code FROM identity.role_permissions rp "
            "JOIN identity.roles r ON r.id = rp.role_id "
            "JOIN identity.permissions p ON p.id = rp.permission_id")).all()
    in_db: dict[str, set[str]] = {}
    for role, code in rows:
        in_db.setdefault(role, set()).add(code)
    assert in_db == {role: {str(p) for p in perms} for role, perms in ROLE_PERMISSIONS.items()}
