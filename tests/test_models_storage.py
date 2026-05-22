from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.models import SessionParseError, parse_session_payload
from app.storage import ProfileStorage


def session_payload(expires: str | None = None) -> dict:
    return {
        "user": {"email": "user@example.com"},
        "accessToken": "access",
        "sessionToken": "session",
        "account": {"id": "account-id"},
        "expires": expires or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "refresh_token": "refresh",
    }


def test_parse_session_payload_maps_required_fields() -> None:
    profile = parse_session_payload(session_payload(), "Профиль 1")

    assert profile.name == "user@example.com"
    assert profile.tokens.access_token == "access"
    assert profile.tokens.id_token == "session"
    assert profile.tokens.account_id == "account-id"
    assert profile.tokens.refresh_token == "refresh"
    assert profile.raw_session["user"]["email"] == "user@example.com"


def test_parse_session_payload_requires_expires() -> None:
    data = session_payload()
    del data["expires"]

    with pytest.raises(SessionParseError) as exc:
        parse_session_payload(json.dumps(data), "Профиль 1")

    assert "expires" in exc.value.missing_fields


def test_storage_exports_active_profile(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    profile = parse_session_payload(session_payload(), "Профиль 1")
    storage.save_profile(profile)

    target = storage.export_profile_to_path(profile.id, str(tmp_path / "export" / "custom-auth.json"))
    data = json.loads(target.read_text(encoding="utf-8"))

    assert target.name == "custom-auth.json"
    assert data["tokens"]["id_token"] == "access"
    assert data["tokens"]["access_token"] == "access"
    assert data["tokens"]["refresh_token"] == "refresh"
    assert data["last_refresh"] == profile.expires
    assert "expires" not in data
    assert "created_at" not in data


def test_storage_exports_rt_123_when_refresh_token_missing(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    payload = session_payload()
    del payload["refresh_token"]
    profile = parse_session_payload(payload, "Профиль 1")
    storage.save_profile(profile)

    target = storage.export_profile_to_path(profile.id, str(tmp_path / "auth.json"))
    data = json.loads(target.read_text(encoding="utf-8"))

    assert data["tokens"]["refresh_token"] == "rt_123"


def test_storage_blocks_expired_export(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    expires = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    profile = parse_session_payload(session_payload(expires), "Профиль 1")
    storage.save_profile(profile)

    with pytest.raises(ValueError):
        storage.export_profile_to_path(profile.id, str(tmp_path / "auth.json"))


def test_activate_profile_sets_selected_and_writes_default_target(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    storage.set_export_path(str(tmp_path / "auth.json"))
    profile = parse_session_payload(session_payload(), "Профиль 1")
    storage.save_profile(profile)

    target = storage.activate_profile(profile.id)
    settings = storage.get_settings()

    assert target == tmp_path / "auth.json"
    assert settings["selected_profile_id"] == profile.id
    assert target.exists()


def test_sync_active_profile_clears_expired_without_touching_file(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    target = tmp_path / "auth.json"
    target.write_text("old", encoding="utf-8")
    active = parse_session_payload(session_payload(), "Профиль 1")
    storage.save_profile(active)
    storage.set_export_path(str(target))
    storage.activate_profile(active.id)

    expired_value = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    active.expires = expired_value
    storage.save_profile(active)
    before = target.read_text(encoding="utf-8")

    assert storage.sync_active_profile() is None
    assert storage.get_settings()["selected_profile_id"] is None
    assert target.read_text(encoding="utf-8") == before


def test_export_creates_backup_before_overwrite(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    target = tmp_path / "auth.json"
    target.write_text("old", encoding="utf-8")
    profile = parse_session_payload(session_payload(), "Профиль 1")
    storage.save_profile(profile)

    storage.export_profile_to_path(profile.id, str(target))

    assert storage.last_backup_path is not None
    assert storage.last_backup_path.exists()
    assert storage.last_backup_path.read_text(encoding="utf-8") == "old"
    assert target.read_text(encoding="utf-8") != "old"


def test_recent_export_paths_are_deduplicated(tmp_path) -> None:
    storage = ProfileStorage(tmp_path)
    first = tmp_path / "one" / "auth.json"
    second = tmp_path / "two" / "auth.json"

    storage.set_export_path(str(first))
    storage.set_export_path(str(second))
    storage.set_export_path(str(first))
    recent = storage.get_settings()["recent_export_paths"]

    assert recent[0] == str(first)
    assert recent[1] == str(second)
    assert recent.count(str(first)) == 1
