from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .models import Profile, utc_now_iso


APP_DIR_NAME = "ChatGPTSessionManager"


class ProfileStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        appdata = os.getenv("APPDATA")
        if base_dir is not None:
            root = base_dir
        elif appdata:
            root = Path(appdata) / APP_DIR_NAME
        else:
            root = Path.home() / f".{APP_DIR_NAME}"
        self.root = Path(root)
        self.profiles_dir = self.root / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir = self.root / "backups"
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "app.log"
        self.settings_path = self.root / "settings.json"
        self.last_backup_path: Path | None = None
        self.root.mkdir(parents=True, exist_ok=True)
        self._normalize_settings()

    def default_export_path(self) -> Path:
        return Path.home() / ".codex" / "auth.json"

    def get_settings(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return self._default_settings()
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            settings = {}
        merged = self._default_settings()
        merged.update({key: value for key, value in settings.items() if key in merged})
        return merged

    def save_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        merged = self._default_settings()
        merged.update({key: value for key, value in settings.items() if key in merged})
        self.settings_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return merged

    def set_export_path(self, export_path: str) -> dict[str, Any]:
        path = Path(export_path).expanduser()
        if not path.name:
            raise ValueError("Укажите имя файла для экспорта.")
        settings = self.get_settings()
        settings["export_path"] = str(path)
        settings["recent_export_paths"] = self._push_recent_export_path(str(path), settings.get("recent_export_paths"))
        return self.save_settings(settings)

    def reset_export_path(self) -> dict[str, Any]:
        settings = self.get_settings()
        export_path = str(self.default_export_path())
        settings["export_path"] = export_path
        settings["recent_export_paths"] = self._push_recent_export_path(export_path, settings.get("recent_export_paths"))
        return self.save_settings(settings)

    def list_profiles(self) -> list[Profile]:
        profiles: list[Profile] = []
        for path in sorted(self.profiles_dir.glob("*.json")):
            try:
                profiles.append(Profile.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(profiles, key=lambda item: item.updated_at, reverse=True)

    def get_profile(self, profile_id: str) -> Profile:
        path = self._path(profile_id)
        if not path.exists():
            raise FileNotFoundError(f"Профиль не найден: {profile_id}")
        return Profile.model_validate_json(path.read_text(encoding="utf-8"))

    def save_profile(self, profile: Profile) -> Profile:
        profile.updated_at = utc_now_iso()
        self._path(profile.id).write_text(
            json.dumps(profile.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return profile

    def delete_profile(self, profile_id: str) -> None:
        self._path(profile_id).unlink(missing_ok=True)
        settings = self.get_settings()
        if settings.get("selected_profile_id") == profile_id:
            settings["selected_profile_id"] = None
            self.save_settings(settings)

    def next_profile_name(self) -> str:
        used = {profile.name for profile in self.list_profiles()}
        index = 1
        while f"Профиль {index}" in used:
            index += 1
        return f"Профиль {index}"

    def export_profile_to_path(self, profile_id: str, export_path: str | None = None) -> Path:
        profile = self.get_profile(profile_id)
        if not profile.is_active:
            raise ValueError("Невозможно экспортировать: сессия истекла. Обновите профиль.")
        target = Path(export_path or self.get_settings()["export_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        self.last_backup_path = self._backup_export_target(target)
        target.write_text(
            json.dumps(profile.to_export(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    def activate_profile(self, profile_id: str) -> Path:
        profile = self.get_profile(profile_id)
        if not profile.is_active:
            raise ValueError("Истёкший профиль нельзя сделать активным.")
        target = self.export_profile_to_path(profile_id)
        settings = self.get_settings()
        settings["selected_profile_id"] = profile_id
        self.save_settings(settings)
        return target

    def sync_active_profile(self) -> Path | None:
        settings = self.get_settings()
        profile_id = settings.get("selected_profile_id")
        if not profile_id:
            return None
        try:
            profile = self.get_profile(str(profile_id))
        except FileNotFoundError:
            settings["selected_profile_id"] = None
            self.save_settings(settings)
            return None
        if not profile.is_active:
            settings["selected_profile_id"] = None
            self.save_settings(settings)
            return None
        return self.export_profile_to_path(profile.id, settings["export_path"])

    def _path(self, profile_id: str) -> Path:
        return self.profiles_dir / f"{profile_id}.json"

    def _default_settings(self) -> dict[str, Any]:
        return {
            "export_path": str(self.default_export_path()),
            "selected_profile_id": None,
            "recent_export_paths": [str(self.default_export_path())],
        }

    def _push_recent_export_path(self, export_path: str, current: Any) -> list[str]:
        recent = [str(item) for item in current if item] if isinstance(current, list) else []
        normalized = str(Path(export_path).expanduser())
        deduped = [item for item in recent if item != normalized]
        return [normalized, *deduped][:8]

    def _backup_export_target(self, target: Path) -> Path | None:
        if not target.exists() or not target.is_file():
            return None
        stamp = utc_now_iso().replace(":", "-").replace(".", "-")
        backup_name = f"{target.name}.{stamp}.bak"
        backup_path = self.backups_dir / backup_name
        shutil.copy2(target, backup_path)
        return backup_path

    def _normalize_settings(self) -> None:
        settings = self.get_settings()
        selected = settings.get("selected_profile_id")
        if selected:
            try:
                profile = self.get_profile(str(selected))
                if not profile.is_active:
                    settings["selected_profile_id"] = None
            except FileNotFoundError:
                settings["selected_profile_id"] = None
        self.save_settings(settings)
