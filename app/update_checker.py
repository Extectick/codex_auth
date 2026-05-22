from __future__ import annotations

import json
import platform
import re
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .version import __version__


REPOSITORY = "Extectick/codex_auth"
LATEST_RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
LATEST_RELEASE_URL = f"https://github.com/{REPOSITORY}/releases/latest"
WINDOWS_X64_ASSET = "ChatGPTSessionManager-windows-x64.exe"
UPDATE_DIR_NAME = "ChatGPTSessionManager"


def check_for_updates(fetcher: Any | None = None) -> dict[str, Any]:
    release = _fetch_latest_release(fetcher)
    latest_version = normalize_version(str(release.get("tag_name", "")))
    if not latest_version:
        raise UpdateCheckError("Latest release response does not contain a valid tag_name.")

    asset = find_platform_asset(release)
    return {
        "current_version": __version__,
        "latest_version": latest_version,
        "has_update": compare_versions(latest_version, __version__) > 0,
        "release_url": release.get("html_url") or LATEST_RELEASE_URL,
        "asset_url": asset.get("browser_download_url") if asset else None,
        "body": release.get("body") or "",
    }


def download_update(asset_url: str, *, downloader: Any | None = None, updates_dir: Path | None = None) -> dict[str, Any]:
    if not asset_url:
        raise UpdateCheckError("Update asset URL is empty.")

    target_dir = updates_dir or Path(tempfile.gettempdir()) / UPDATE_DIR_NAME / "updates"
    target_dir.mkdir(parents=True, exist_ok=True)
    exe_path = target_dir / WINDOWS_X64_ASSET
    sha_path = target_dir / f"{WINDOWS_X64_ASSET}.sha256"

    exe_bytes = _download_bytes(asset_url, downloader)
    checksum_bytes = _download_bytes(f"{asset_url}.sha256", downloader)
    expected_hash = parse_sha256_text(checksum_bytes.decode("ascii", errors="replace"))
    actual_hash = sha256(exe_bytes).hexdigest().upper()
    if actual_hash != expected_hash.upper():
        raise UpdateCheckError("Downloaded update checksum does not match SHA256 file.")

    exe_path.write_bytes(exe_bytes)
    sha_path.write_text(f"{expected_hash.upper()}  {WINDOWS_X64_ASSET}", encoding="ascii")
    return {
        "path": str(exe_path),
        "sha256_path": str(sha_path),
        "sha256": actual_hash,
    }


def parse_sha256_text(value: str) -> str:
    token = value.strip().split()[0] if value.strip() else ""
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", token):
        raise UpdateCheckError("SHA256 file does not contain a valid checksum.")
    return token


def compare_versions(left: str, right: str) -> int:
    left_parts = parse_semver(left)
    right_parts = parse_semver(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def parse_semver(value: str) -> tuple[int, int, int]:
    normalized = normalize_version(value)
    if not normalized:
        raise ValueError(f"Invalid semantic version: {value}")
    return tuple(int(part) for part in normalized.split("."))  # type: ignore[return-value]


def normalize_version(value: str) -> str:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return ""
    return ".".join(match.groups())


def platform_asset_name() -> str | None:
    if platform.system() == "Windows" and platform.machine().lower() in {"amd64", "x86_64"}:
        return WINDOWS_X64_ASSET
    return None


def find_platform_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    expected_name = platform_asset_name()
    if not expected_name:
        return None
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == expected_name:
            return asset
    return None


def _fetch_latest_release(fetcher: Any | None = None) -> dict[str, Any]:
    if fetcher is not None:
        data = fetcher()
    else:
        request = Request(
            LATEST_RELEASE_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "ChatGPTSessionManager",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise UpdateCheckError(f"GitHub release check failed with HTTP {exc.code}.") from exc
        except URLError as exc:
            raise UpdateCheckError(f"GitHub release check failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise UpdateCheckError("GitHub release check timed out.") from exc
        except json.JSONDecodeError as exc:
            raise UpdateCheckError("GitHub release response is not valid JSON.") from exc

    if not isinstance(data, dict):
        raise UpdateCheckError("GitHub release response is not a JSON object.")
    return data


def _download_bytes(url: str, downloader: Any | None = None) -> bytes:
    if downloader is not None:
        data = downloader(url)
        if not isinstance(data, bytes):
            raise UpdateCheckError("Downloader did not return bytes.")
        return data

    request = Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "ChatGPTSessionManager",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        raise UpdateCheckError(f"Update download failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise UpdateCheckError(f"Update download failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise UpdateCheckError("Update download timed out.") from exc


class UpdateCheckError(RuntimeError):
    pass
