"""Shared validation for document URLs and remote file paths."""

from urllib.parse import quote, unquote


def validate_identifier(value: str, name: str) -> str:
    """Reject identifiers containing path separators or control characters."""
    if (
        not value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


def quote_segment(value: str) -> str:
    """Quote a single identifier for insertion into a URL."""
    return quote(value, safe="")


def validate_document_path(value: str) -> str:
    """Constrain remote metadata to a relative path below the docs endpoint."""
    decoded = unquote(value)
    if (
        any(character in decoded for character in "\\?#:%")
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded)
        or any(part in {"", ".", ".."} for part in decoded.split("/"))
    ):
        raise ValueError("Invalid document path in metadata")
    return "/".join(quote_segment(part) for part in decoded.split("/"))


def document_url(docs_url: str, path: str) -> str:
    """Build a constrained document URL below the configured endpoint."""
    return f"{docs_url.rstrip('/')}/{validate_document_path(path)}"
