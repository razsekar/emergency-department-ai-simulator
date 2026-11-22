"""Talks to a local Ollama service to discover installed models (GET /api/tags)."""
import httpx


def list_models(base_url: str, timeout: float = 3.0) -> list[str]:
    """Return installed model names. Raises httpx.HTTPError if Ollama is unreachable."""
    resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", []) if "name" in m]
