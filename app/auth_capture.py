from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import webview


SESSION_JS = r"""
(async function () {
  function cookieValue(name) {
    const found = document.cookie.split('; ').find(row => row.startsWith(name + '='));
    return found ? decodeURIComponent(found.split('=').slice(1).join('=')) : null;
  }
  const response = await fetch('/api/auth/session/', { credentials: 'include' });
  if (!response.ok) {
    throw new Error('HTTP ' + response.status);
  }
  const payload = await response.json();
  payload.refresh_token = cookieValue('__Secure-next-auth.session-token');
  return payload;
})();
"""


@dataclass
class CaptureResult:
    ok: bool
    payload: dict[str, Any] | None = None
    error: str | None = None


class AuthCapture:
    def capture(self) -> CaptureResult:
        done = threading.Event()
        result: dict[str, Any] = {"value": CaptureResult(ok=False, error="Авторизация отменена")}

        window = webview.create_window(
            "Вход в ChatGPT",
            "https://chatgpt.com/auth/login",
            width=1100,
            height=800,
            text_select=True,
        )

        def on_closed() -> None:
            if not done.is_set():
                result["value"] = CaptureResult(ok=False, error="Авторизация отменена")
                done.set()

        window.events.closed += on_closed

        def worker() -> None:
            while not done.is_set():
                try:
                    current_url = window.get_current_url()
                    if current_url and current_url.rstrip("/") == "https://chatgpt.com":
                        payload = window.evaluate_js(SESSION_JS)
                        if isinstance(payload, dict):
                            result["value"] = CaptureResult(ok=True, payload=payload)
                        else:
                            result["value"] = CaptureResult(ok=False, error="Ответ сессии имеет неожиданный формат")
                        done.set()
                        try:
                            window.destroy()
                        except Exception:
                            pass
                        return
                except Exception as exc:
                    result["value"] = CaptureResult(ok=False, error=str(exc))
                time.sleep(1)

        threading.Thread(target=worker, daemon=True).start()
        done.wait()
        return result["value"]
