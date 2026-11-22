"""Knowledge Base configuration (environment-driven, module-owned)."""
import os


def max_upload_bytes() -> int:
    return int(os.environ.get("KB_MAX_UPLOAD_MB", "10")) * 1024 * 1024


def max_pages() -> int:
    return int(os.environ.get("KB_MAX_PAGES", "300"))


def sample_docs_dir() -> str:
    return os.environ.get("KB_SAMPLE_DOCS_DIR", "/sample_docs")
