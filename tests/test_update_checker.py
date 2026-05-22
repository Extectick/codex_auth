from __future__ import annotations

import pytest
from hashlib import sha256

from app import update_checker
from app.update_checker import compare_versions, find_platform_asset, normalize_version, parse_sha256_text


def release_payload(tag_name: str = "v0.2.0") -> dict:
    return {
        "tag_name": tag_name,
        "html_url": "https://github.com/Extectick/codex_auth/releases/tag/v0.2.0",
        "body": "Release notes",
        "assets": [
            {
                "name": "ChatGPTSessionManager-windows-x64.exe",
                "browser_download_url": "https://example.test/app.exe",
            }
        ],
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("v0.1.0", "0.1.0"),
        ("0.1.0", "0.1.0"),
        (" v10.20.30 ", "10.20.30"),
        ("latest", ""),
    ],
)
def test_normalize_version(raw: str, expected: str) -> None:
    assert normalize_version(raw) == expected


def test_compare_versions() -> None:
    assert compare_versions("0.2.0", "0.1.0") == 1
    assert compare_versions("0.1.0", "0.1.0") == 0
    assert compare_versions("0.1.0", "0.2.0") == -1


def test_find_platform_asset_for_windows_x64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_checker.platform, "system", lambda: "Windows")
    monkeypatch.setattr(update_checker.platform, "machine", lambda: "AMD64")

    asset = find_platform_asset(release_payload())

    assert asset is not None
    assert asset["browser_download_url"] == "https://example.test/app.exe"


def test_check_for_updates_maps_latest_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_checker.platform, "system", lambda: "Windows")
    monkeypatch.setattr(update_checker.platform, "machine", lambda: "AMD64")

    result = update_checker.check_for_updates(fetcher=lambda: release_payload("v0.2.0"))

    assert result == {
        "current_version": "0.1.0",
        "latest_version": "0.2.0",
        "has_update": True,
        "release_url": "https://github.com/Extectick/codex_auth/releases/tag/v0.2.0",
        "asset_url": "https://example.test/app.exe",
        "body": "Release notes",
    }


def test_check_for_updates_rejects_invalid_tag() -> None:
    with pytest.raises(update_checker.UpdateCheckError):
        update_checker.check_for_updates(fetcher=lambda: release_payload("not-a-version"))


def test_parse_sha256_text() -> None:
    checksum = "A" * 64
    assert parse_sha256_text(f"{checksum}  ChatGPTSessionManager-windows-x64.exe") == checksum


def test_download_update_verifies_checksum(tmp_path) -> None:
    exe_bytes = b"fake exe"
    checksum = sha256(exe_bytes).hexdigest().upper()

    def downloader(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{checksum}  ChatGPTSessionManager-windows-x64.exe".encode("ascii")
        return exe_bytes

    result = update_checker.download_update("https://example.test/app.exe", downloader=downloader, updates_dir=tmp_path)

    assert result["sha256"] == checksum
    assert (tmp_path / "ChatGPTSessionManager-windows-x64.exe").read_bytes() == exe_bytes
    assert (tmp_path / "ChatGPTSessionManager-windows-x64.exe.sha256").exists()


def test_download_update_rejects_bad_checksum(tmp_path) -> None:
    def downloader(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{'0' * 64}  ChatGPTSessionManager-windows-x64.exe".encode("ascii")
        return b"fake exe"

    with pytest.raises(update_checker.UpdateCheckError):
        update_checker.download_update("https://example.test/app.exe", downloader=downloader, updates_dir=tmp_path)
