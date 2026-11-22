"""Identity settings read from the environment (server-side only)."""
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.modules.identity.domain.errors import AuthNotConfiguredError

MIN_SECRET_LENGTH = 32


class IdentitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = ""
    jwt_ttl_minutes: int = 60
    demo_admin_password: str = ""
    demo_presenter_password: str = ""
    demo_viewer_password: str = ""

    def require_signing_secret(self) -> str:
        if len(self.jwt_secret) < MIN_SECRET_LENGTH:
            raise AuthNotConfiguredError("Authentication is not configured on the server")
        return self.jwt_secret
