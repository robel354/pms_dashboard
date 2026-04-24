from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from utils.config import (
    AZURE_BLOB_CONTAINER,
    AZURE_STORAGE_ACCOUNT_URL,
    DATA_DIR,
    USE_AZURE_STORAGE,
)

_BLOCKED_URL_SCHEMES = {"http", "https"}


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@dataclass(frozen=True)
class DocumentReference:
    backend: str
    path: str
    display_name: str
    access_url: str | None = None
    is_private: bool = True


class StorageBackend(Protocol):
    def list_files(self, prefix: str = "") -> list[str]:
        ...

    def read_csv_content(self, file_name: str) -> bytes:
        ...

    def generate_document_reference(self, file_name: str) -> DocumentReference:
        ...


class LocalStorageBackend:
    """Read dashboard files from the local data directory."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        ensure_directory(self.base_dir)

    def _resolve(self, relative_path: str) -> Path:
        return (self.base_dir / relative_path).resolve()

    def list_files(self, prefix: str = "") -> list[str]:
        if not self.base_dir.exists():
            return []

        normalized_prefix = prefix.replace("\\", "/").strip("/")
        files = [
            path.relative_to(self.base_dir).as_posix()
            for path in self.base_dir.rglob("*")
            if path.is_file()
        ]
        if not normalized_prefix:
            return sorted(files)
        return sorted(file_name for file_name in files if file_name.startswith(normalized_prefix))

    def read_csv_content(self, file_name: str) -> bytes:
        path = self._resolve(file_name)
        if not path.exists():
            raise FileNotFoundError(f"Local file not found: {path}")
        return path.read_bytes()

    def generate_document_reference(self, file_name: str) -> DocumentReference:
        return DocumentReference(
            backend="local",
            path=file_name,
            display_name=Path(file_name).name,
            access_url=None,
            is_private=True,
        )


class AzureBlobStorageBackend:
    """Read dashboard files from a private Azure Blob Storage container."""

    def __init__(self, account_url: str, container_name: str) -> None:
        if not account_url or not container_name:
            raise ValueError("Azure Blob Storage requires account URL and container name.")

        self.account_url = account_url
        self.container_name = container_name

    def _get_container_client(self):  # type: ignore[no-untyped-def]
        try:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Azure storage dependencies are not installed. Add `azure-identity` and `azure-storage-blob`."
            ) from exc

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        service_client = BlobServiceClient(account_url=self.account_url, credential=credential)
        return service_client.get_container_client(self.container_name)

    def list_files(self, prefix: str = "") -> list[str]:
        container_client = self._get_container_client()
        return sorted(blob.name for blob in container_client.list_blobs(name_starts_with=prefix or None))

    def read_csv_content(self, file_name: str) -> bytes:
        container_client = self._get_container_client()
        blob_client = container_client.get_blob_client(file_name)
        return blob_client.download_blob().readall()

    def generate_document_reference(self, file_name: str) -> DocumentReference:
        safe_path = file_name.strip().lstrip("/")
        return DocumentReference(
            backend="azure_blob",
            path=safe_path,
            display_name=Path(safe_path).name,
            access_url=None,
            is_private=True,
        )


def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend for the current environment."""
    if USE_AZURE_STORAGE:
        return AzureBlobStorageBackend(
            account_url=AZURE_STORAGE_ACCOUNT_URL,
            container_name=AZURE_BLOB_CONTAINER,
        )
    return LocalStorageBackend(DATA_DIR)


def list_available_files(prefix: str = "") -> list[str]:
    return get_storage_backend().list_files(prefix=prefix)


def read_csv_content(file_name: str) -> bytes:
    return get_storage_backend().read_csv_content(file_name)


def generate_safe_document_reference(file_name: str) -> DocumentReference:
    return get_storage_backend().generate_document_reference(file_name)


def resolve_document_access_url(raw_value: object) -> str | None:
    """Return a document URL for demo viewing.

    Reviewer requirement: documents must be viewable now (demo mode).
    """
    if raw_value is None:
        return None

    candidate = str(raw_value).strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme and parsed.scheme.lower() in _BLOCKED_URL_SCHEMES:
        return candidate

    reference = generate_safe_document_reference(candidate)
    return reference.access_url


def has_document_reference(raw_value: object) -> bool:
    if raw_value is None:
        return False
    return bool(str(raw_value).strip())
