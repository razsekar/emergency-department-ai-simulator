"""Typed request/response contracts of the identity module."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """The authenticated principal, resolved fresh from the database on every request."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    username: str
    display_name: str
    roles: tuple[str, ...]
    permissions: frozenset[str]

    def has_permission(self, code: str) -> bool:
        return str(code) in self.permissions


class LoginResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUser
