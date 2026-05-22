from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


class TokenSet(BaseModel):
    id_token: str
    access_token: str
    refresh_token: str | None = None
    account_id: str


class Profile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    auth_mode: str = "chatgpt"
    OPENAI_API_KEY: str | None = None
    tokens: TokenSet
    raw_session: dict[str, Any] = Field(default_factory=dict)
    last_refresh: str = Field(default_factory=utc_now_iso)
    expires: str
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @property
    def is_active(self) -> bool:
        try:
            return parse_datetime(self.expires) > datetime.now(timezone.utc)
        except Exception:
            return False

    def to_card(self) -> dict[str, Any]:
        data = self.model_dump()
        data["is_active"] = self.is_active
        return data

    def to_export(self) -> dict[str, Any]:
        return {
            "auth_mode": self.auth_mode,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
            "tokens": {
                "id_token": self.tokens.access_token,
                "access_token": self.tokens.access_token,
                "refresh_token": self.tokens.refresh_token or "rt_123",
                "account_id": self.tokens.account_id,
            },
            "last_refresh": self.expires,
        }


class SessionParseError(ValueError):
    def __init__(self, message: str, missing_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields or []


def _get_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def parse_session_payload(raw: str | dict[str, Any], fallback_name: str) -> Profile:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SessionParseError(f"Некорректный формат JSON: {exc.msg} (строка {exc.lineno}, столбец {exc.colno})") from exc
    else:
        data = raw

    if not isinstance(data, dict):
        raise SessionParseError("Некорректный формат JSON: ожидается объект")

    required = {
        "accessToken": _get_path(data, "accessToken"),
        "sessionToken": _get_path(data, "sessionToken"),
        "account.id": _get_path(data, "account.id"),
        "expires": _get_path(data, "expires"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SessionParseError("Отсутствует " + ", ".join(missing), missing)

    user_email = _get_path(data, "user.email")
    user_name = _get_path(data, "user.name")
    profile_name = str(user_email or user_name or fallback_name)

    refresh_token = data.get("refresh_token")
    if refresh_token is None:
        refresh_token = data.get("refreshToken")

    now = utc_now_iso()
    return Profile(
        name=profile_name,
        tokens=TokenSet(
            id_token=str(required["sessionToken"]),
            access_token=str(required["accessToken"]),
            refresh_token=str(refresh_token) if refresh_token else None,
            account_id=str(required["account.id"]),
        ),
        raw_session=data,
        last_refresh=now,
        expires=str(required["expires"]),
        created_at=now,
        updated_at=now,
    )
