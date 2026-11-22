"""Upload validation rules (PDF only, size-limited)."""
from app.platform.errors import AppError, NotFoundError  # noqa: F401  (re-exported for callers)


class UploadRejected(AppError):
    status_code = 400
    code = "upload_rejected"


class UnsupportedFileType(UploadRejected):
    status_code = 415
    code = "unsupported_file_type"


class FileTooLarge(UploadRejected):
    status_code = 413
    code = "file_too_large"


class UnreadableDocument(UploadRejected):
    status_code = 422
    code = "unreadable_document"


class DuplicateDocument(AppError):
    status_code = 409
    code = "duplicate_document"


def validate_pdf_upload(filename: str | None, data: bytes, max_bytes: int) -> None:
    """Reject anything that is not a non-empty, size-limited PDF (extension AND magic bytes)."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise UnsupportedFileType("Only PDF files (.pdf) are supported.")
    if len(data) == 0:
        raise UploadRejected("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise FileTooLarge(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")
    if not data.startswith(b"%PDF-"):
        raise UnsupportedFileType("The file content is not a PDF.")
