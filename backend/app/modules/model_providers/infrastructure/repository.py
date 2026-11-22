"""Persistence for model_providers.model_configurations (this module's own table only)."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def list_enabled(session: Session) -> list[dict]:
    rows = session.execute(
        text(
            "SELECT provider, model_id, COALESCE(display_name, model_id) AS display_name "
            "FROM model_providers.model_configurations WHERE enabled ORDER BY provider, model_id"
        )
    ).mappings()
    return [dict(r) for r in rows]


def upsert(session: Session, provider: str, model_id: str, display_name: str | None) -> None:
    session.execute(
        text(
            "INSERT INTO model_providers.model_configurations (provider, model_id, display_name, enabled) "
            "VALUES (:p, :m, :d, true) "
            "ON CONFLICT (provider, model_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
            "enabled = true, updated_at = now()"
        ),
        {"p": provider, "m": model_id, "d": display_name},
    )


def disable(session: Session, provider: str, model_id: str) -> bool:
    res = session.execute(
        text(
            "UPDATE model_providers.model_configurations SET enabled = false, updated_at = now() "
            "WHERE provider = :p AND model_id = :m AND enabled"
        ),
        {"p": provider, "m": model_id},
    )
    return res.rowcount > 0
