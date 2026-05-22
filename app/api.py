from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

import webview

from .auth_capture import AuthCapture
from .models import SessionParseError, parse_session_payload, utc_now_iso
from .storage import ProfileStorage
from .update_checker import LATEST_RELEASE_URL, check_for_updates as get_update_status, download_update as fetch_update
from .version import __version__


class AppApi:
    def __init__(self, storage: ProfileStorage | None = None, auth_capture: AuthCapture | None = None) -> None:
        self.storage = storage or ProfileStorage()
        self.auth_capture = auth_capture or AuthCapture()
        self.logger = logging.getLogger("chatgpt_session_manager")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            handler = logging.FileHandler(self.storage.log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)

    def list_profiles(self) -> dict[str, Any]:
        settings = self.storage.get_settings()
        selected_id = settings.get("selected_profile_id")
        if selected_id:
            try:
                if not self.storage.get_profile(str(selected_id)).is_active:
                    settings["selected_profile_id"] = None
                    self.storage.save_settings(settings)
            except FileNotFoundError:
                settings["selected_profile_id"] = None
                self.storage.save_settings(settings)
        return self._ok(
            profiles=[profile.to_card() for profile in self.storage.list_profiles()],
            storage_path=str(self.storage.profiles_dir),
            settings=settings,
        )

    def get_app_info(self) -> dict[str, Any]:
        return self._ok(name="ChatGPT Session Manager", version=__version__)

    def check_for_updates(self) -> dict[str, Any]:
        try:
            return self._ok(**get_update_status())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def open_latest_release(self) -> dict[str, Any]:
        try:
            webbrowser.open(LATEST_RELEASE_URL)
            return self._ok(release_url=LATEST_RELEASE_URL)
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def download_update(self, asset_url: str) -> dict[str, Any]:
        try:
            return self._ok(**fetch_update(asset_url))
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def open_downloaded_update(self, path: str) -> dict[str, Any]:
        try:
            os.startfile(str(Path(path)))  # type: ignore[attr-defined]
            return self._ok(path=path)
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def install_update(self, path: str) -> dict[str, Any]:
        try:
            source = Path(path)
            if not source.exists():
                return self._error(f"Файл обновления не найден: {source}")
            updater = self._updater_path()
            target = Path(sys.executable if getattr(sys, "frozen", False) else Path.cwd() / "dist" / "ChatGPTSessionManager.exe")
            if not target.exists():
                return self._error(f"Целевой exe не найден: {target}")
            subprocess.Popen(
                [
                    str(updater),
                    "--pid",
                    str(os.getpid()),
                    "--source",
                    str(source),
                    "--target",
                    str(target),
                ],
                close_fds=True,
            )
            threading.Timer(0.5, self._close_window).start()
            return self._ok()
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def create_manual_profile(self, raw_json: str) -> dict[str, Any]:
        try:
            profile = parse_session_payload(raw_json, self.storage.next_profile_name())
            self.storage.save_profile(profile)
            return self._ok(profile=profile.to_card())
        except SessionParseError as exc:
            return self._error(str(exc), exc=exc, missing_fields=exc.missing_fields)
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def create_auto_profile(self) -> dict[str, Any]:
        capture = self.auth_capture.capture()
        if not capture.ok or not capture.payload:
            return self._error(capture.error or "Не удалось автоматически получить сессию.")
        try:
            profile = parse_session_payload(capture.payload, self.storage.next_profile_name())
            self.storage.save_profile(profile)
            return self._ok(profile=profile.to_card())
        except SessionParseError as exc:
            return self._error(str(exc), exc=exc, missing_fields=exc.missing_fields)
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def refresh_profile(self, profile_id: str) -> dict[str, Any]:
        capture = self.auth_capture.capture()
        if not capture.ok or not capture.payload:
            return self._error(capture.error or "Не удалось автоматически получить сессию.")
        try:
            current = self.storage.get_profile(profile_id)
            incoming = parse_session_payload(capture.payload, current.name)
            current.tokens = incoming.tokens
            current.expires = incoming.expires
            current.raw_session = incoming.raw_session
            current.last_refresh = utc_now_iso()
            self.storage.save_profile(current)
            synced_path = self.storage.sync_active_profile()
            return self._ok(profile=current.to_card(), synced_path=str(synced_path) if synced_path else None)
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def rename_profile(self, profile_id: str, name: str) -> dict[str, Any]:
        cleaned = (name or "").strip()
        if not cleaned:
            return self._error("Название профиля не может быть пустым.")
        try:
            profile = self.storage.get_profile(profile_id)
            profile.name = cleaned
            self.storage.save_profile(profile)
            return self._ok(profile=profile.to_card())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        try:
            self.storage.delete_profile(profile_id)
            return self._ok()
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def activate_profile(self, profile_id: str) -> dict[str, Any]:
        try:
            target = self.storage.activate_profile(profile_id)
            return self._ok(path=str(target), backup_path=self._last_backup())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def write_active_profile(self) -> dict[str, Any]:
        try:
            target = self.storage.sync_active_profile()
            if not target:
                return self._error("Активный профиль не выбран или истёк.")
            return self._ok(path=str(target), backup_path=self._last_backup())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def choose_export_file(self) -> dict[str, Any]:
        try:
            current = Path(self.storage.get_settings()["export_path"])
            files = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                directory=str(current.parent),
                save_filename=current.name,
                file_types=("JSON files (*.json)", "All files (*.*)"),
            )
            if not files:
                return self._error("Файл не выбран.", log=False)
            selected = files[0] if isinstance(files, (list, tuple)) else files
            settings = self.storage.set_export_path(str(selected))
            synced_path = self.storage.sync_active_profile()
            return self._ok(settings=settings, synced_path=str(synced_path) if synced_path else None, backup_path=self._last_backup())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def set_export_path(self, export_path: str) -> dict[str, Any]:
        try:
            settings = self.storage.set_export_path(export_path)
            synced_path = self.storage.sync_active_profile()
            return self._ok(settings=settings, synced_path=str(synced_path) if synced_path else None, backup_path=self._last_backup())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def reset_export_path(self) -> dict[str, Any]:
        try:
            settings = self.storage.reset_export_path()
            synced_path = self.storage.sync_active_profile()
            return self._ok(settings=settings, synced_path=str(synced_path) if synced_path else None, backup_path=self._last_backup())
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def read_json_file(self) -> dict[str, Any]:
        try:
            files = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=("JSON files (*.json)", "All files (*.*)"),
            )
            if not files:
                return self._error("Файл не выбран.", log=False)
            path = Path(files[0])
            return self._ok(content=path.read_text(encoding="utf-8"), path=str(path))
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def open_session_url(self) -> dict[str, Any]:
        try:
            webbrowser.open("https://chatgpt.com/api/auth/session/")
            return self._ok()
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def open_profiles_folder(self) -> dict[str, Any]:
        try:
            os.startfile(str(self.storage.profiles_dir))  # type: ignore[attr-defined]
            return self._ok(path=str(self.storage.profiles_dir))
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def open_export_file(self) -> dict[str, Any]:
        try:
            path = Path(self.storage.get_settings()["export_path"])
            if path.exists():
                os.startfile(str(path))  # type: ignore[attr-defined]
                return self._ok(path=str(path))
            os.startfile(str(path.parent))  # type: ignore[attr-defined]
            return self._ok(path=str(path.parent))
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def read_logs(self) -> dict[str, Any]:
        try:
            if not self.storage.log_path.exists():
                return self._ok(content="", path=str(self.storage.log_path))
            return self._ok(content=self.storage.log_path.read_text(encoding="utf-8"), path=str(self.storage.log_path))
        except Exception as exc:
            return self._error(str(exc), exc=exc)

    def _ok(self, **payload: Any) -> dict[str, Any]:
        return {"ok": True, **payload}

    def _last_backup(self) -> str | None:
        return str(self.storage.last_backup_path) if self.storage.last_backup_path else None

    def _updater_path(self) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        candidates = [
            base / "updater" / "updater.exe",
            Path.cwd() / "dist" / "updater.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError("updater.exe не найден.")

    def _close_window(self) -> None:
        if webview.windows:
            webview.windows[0].destroy()

    def _error(self, message: str, *, exc: Exception | None = None, log: bool = True, **payload: Any) -> dict[str, Any]:
        if log:
            if exc is not None:
                self.logger.exception(message)
            else:
                self.logger.error(message)
        return {"ok": False, "error": message, **payload}
