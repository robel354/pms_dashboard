from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _parse_csv_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_bool(raw_value: str, default: bool = False) -> bool:
    if not raw_value:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


APP_TITLE: Final[str] = _get_env("APP_TITLE", "Recipient Dashboard")
PAGE_ICON: Final[str] = _get_env("PAGE_ICON", ":seedling:")
APP_ENV: Final[str] = _get_env("APP_ENV", "development")
ENTITY_NAME: Final[str] = _get_env("ENTITY_NAME", "Farmer")
AUTH_ENABLED: Final[bool] = _parse_bool(_get_env("AUTH_ENABLED", "false"))
DATA_DIR: Final[Path] = (BASE_DIR / _get_env("DATA_DIR", "data")).resolve()
ALLOWED_EMAILS: Final[list[str]] = _parse_csv_list(_get_env("ALLOWED_EMAILS", ""))
ALLOWED_DOMAINS: Final[list[str]] = _parse_csv_list(_get_env("ALLOWED_DOMAINS", ""))
ALLOW_SENSITIVE_UNMASK: Final[bool] = _parse_bool(_get_env("ALLOW_SENSITIVE_UNMASK", "false"))
USE_AZURE_STORAGE: Final[bool] = _parse_bool(_get_env("USE_AZURE_STORAGE", "false"))
AZURE_STORAGE_ACCOUNT_URL: Final[str] = _get_env("AZURE_STORAGE_ACCOUNT_URL", "")
AZURE_BLOB_CONTAINER: Final[str] = _get_env("AZURE_BLOB_CONTAINER", "")
