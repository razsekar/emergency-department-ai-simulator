"""Persistence for the identity module. Private: other modules must use identity.public."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.infrastructure.models import (
    PermissionRow, RolePermissionRow, RoleRow, UserRoleRow, UserRow,
)


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def find_user_by_username(self, username: str) -> UserRow | None:
        return self._s.scalar(select(UserRow).where(UserRow.username == username))

    def get_user(self, user_id: uuid.UUID) -> UserRow | None:
        return self._s.get(UserRow, user_id)

    def role_names(self, user_id: uuid.UUID) -> list[str]:
        stmt = (
            select(RoleRow.name)
            .join(UserRoleRow, UserRoleRow.role_id == RoleRow.id)
            .where(UserRoleRow.user_id == user_id)
            .order_by(RoleRow.name)
        )
        return list(self._s.scalars(stmt))

    def permission_codes(self, user_id: uuid.UUID) -> set[str]:
        stmt = (
            select(PermissionRow.code)
            .join(RolePermissionRow, RolePermissionRow.permission_id == PermissionRow.id)
            .join(UserRoleRow, UserRoleRow.role_id == RolePermissionRow.role_id)
            .where(UserRoleRow.user_id == user_id)
            .distinct()
        )
        return set(self._s.scalars(stmt))

    def create_user(self, username: str, display_name: str, password_hash: str) -> UserRow:
        user = UserRow(username=username, display_name=display_name, password_hash=password_hash)
        self._s.add(user)
        self._s.flush()
        return user

    def assign_role(self, user_id: uuid.UUID, role_name: str) -> None:
        role = self._s.scalar(select(RoleRow).where(RoleRow.name == role_name))
        if role is None:
            raise ValueError(f"unknown role: {role_name}")
        exists = self._s.get(UserRoleRow, (user_id, role.id))
        if exists is None:
            self._s.add(UserRoleRow(user_id=user_id, role_id=role.id))
            self._s.flush()

    def ensure_reference_data(self, role_permissions: dict[str, set[str]]) -> None:
        """Idempotently make roles, permissions and their links match the given matrix."""
        codes = {c for perms in role_permissions.values() for c in perms}
        perm_ids: dict[str, uuid.UUID] = {}
        for code in sorted(codes):
            row = self._s.scalar(select(PermissionRow).where(PermissionRow.code == code))
            if row is None:
                row = PermissionRow(code=code)
                self._s.add(row)
                self._s.flush()
            perm_ids[code] = row.id
        for name, perms in role_permissions.items():
            role = self._s.scalar(select(RoleRow).where(RoleRow.name == name))
            if role is None:
                role = RoleRow(name=name)
                self._s.add(role)
                self._s.flush()
            for code in perms:
                if self._s.get(RolePermissionRow, (role.id, perm_ids[code])) is None:
                    self._s.add(RolePermissionRow(role_id=role.id, permission_id=perm_ids[code]))
        self._s.flush()
