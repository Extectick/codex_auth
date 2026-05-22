from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pystray

    from .api import AppApi


class TrayController:
    def __init__(self, api: "AppApi", icon_path: Path) -> None:
        import pystray
        from PIL import Image

        self.api = api
        self.pystray = pystray
        self.icon = pystray.Icon("ChatGPTSessionManager", Image.open(icon_path), "ChatGPT Session Manager")
        self.icon.menu = self.build_menu()

    def run(self) -> "pystray.Icon":
        self.icon.run_detached()
        return self.icon

    def build_menu(self) -> "pystray.Menu":
        items = [
            self.pystray.MenuItem("Записать активный профиль", self.write_active),
            self.pystray.Menu.SEPARATOR,
            *self.profile_items(),
            self.pystray.Menu.SEPARATOR,
            self.pystray.MenuItem("Обновить меню", self.refresh_menu),
            self.pystray.MenuItem("Выход", self.quit_app),
        ]
        return self.pystray.Menu(*items)

    def profile_items(self) -> list["pystray.MenuItem"]:
        profiles = self.api.storage.list_profiles()
        settings = self.api.storage.get_settings()
        selected_id = settings.get("selected_profile_id")
        items = []
        for profile in profiles[:12]:
            label = f"* {profile.name}" if selected_id == profile.id else profile.name
            items.append(
                self.pystray.MenuItem(
                    label,
                    self.make_activate_handler(profile.id),
                    enabled=profile.is_active,
                )
            )
        if not items:
            items.append(self.pystray.MenuItem("Профилей нет", self.noop, enabled=False))
        return items

    def make_activate_handler(self, profile_id: str):
        def activate(_icon, _item) -> None:
            result = self.api.activate_profile(profile_id)
            if not result.get("ok"):
                self.api.logger.error("Tray profile activation failed: %s", result.get("error"))
            self.refresh_menu(_icon, _item)

        return activate

    def write_active(self, _icon, _item) -> None:
        result = self.api.write_active_profile()
        if not result.get("ok"):
            self.api.logger.error("Tray active profile write failed: %s", result.get("error"))

    def refresh_menu(self, _icon, _item) -> None:
        self.icon.menu = self.build_menu()
        self.icon.update_menu()

    def quit_app(self, _icon, _item) -> None:
        import webview

        self.icon.stop()
        if webview.windows:
            webview.windows[0].destroy()

    def noop(self, _icon, _item) -> None:
        return None


def start_tray(api: "AppApi", icon_path: Path) -> "pystray.Icon | None":
    try:
        return TrayController(api, icon_path).run()
    except Exception as exc:
        api.logger.exception("Tray icon failed to start: %s", exc)
        return None
