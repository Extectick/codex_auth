# План разработки: Open Source, Releases, CI/CD и обновления

## Цель

Подготовить проект к публикации на GitHub как open source приложение и добавить управляемый цикл релизов:

- чистый репозиторий без локальных артефактов и токенов;
- красивый README и базовые open source документы;
- GitHub Actions для проверок и сборки;
- GitHub Releases для версий приложения;
- проверка обновлений внутри приложения;
- безопасная схема установки обновлений.

## Важные решения

- Не публиковать каждый commit в `main` как пользовательскую версию.
- `main` должен запускать CI и собирать dev-artifact.
- Пользовательские версии выпускать только через git tags формата `vX.Y.Z`.
- Приложение должно проверять только GitHub Releases, а не скачивать исходники из `main`.
- На первом этапе обновления приложение открывает страницу релиза или скачивает готовый `.exe`.
- Полная замена запущенного `.exe` делается отдельным `updater.exe` на следующем этапе.

## Этап 1. Подготовка репозитория

Добавить файлы:

- `.gitignore`
- `LICENSE`
- `SECURITY.md`
- `CHANGELOG.md`
- `app/version.py`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

`.gitignore` должен исключать:

```gitignore
.venv/
dist/
build/
__pycache__/
.pytest_cache/
*.pyc
*.log
.env

# local user/session data
auth.json
profiles/
settings.json
app.log
*.token
```

`app/version.py`:

```python
__version__ = "0.1.0"
```

Версию использовать в UI и в update checker.

## Этап 2. README и документация

Переписать `README.md` со структурой:

- название и краткое описание;
- скриншот приложения;
- предупреждение о безопасности токенов;
- ссылка на Latest Release;
- таблица платформ:

```md
| Platform | Status | Artifact |
|---|---|---|
| Windows x64 | Supported | ChatGPTSessionManager-windows-x64.exe |
| Linux x64 | Planned | - |
| macOS | Planned | - |
```

- установка для пользователя;
- запуск из исходников;
- сборка из исходников;
- где хранятся профили и настройки;
- формат экспортируемого `auth.json`;
- release process для maintainer;
- license/security.

`CHANGELOG.md` вести в формате:

```md
# Changelog

## 0.1.0
- Initial Windows release.
```

`SECURITY.md` должен явно сказать:

- профили и токены хранятся локально открытым текстом;
- не прикладывать `auth.json` и профили к issues;
- как сообщать о security проблемах.

## Этап 3. CI для main и pull requests

Создать `.github/workflows/ci.yml`.

Триггеры:

```yaml
on:
  push:
    branches: [main]
  pull_request:
```

Jobs:

- `test` на `windows-latest`;
- checkout;
- setup Python 3.13 или 3.12;
- install dependencies;
- `python -m compileall app tests`;
- `python -m pytest -q`;
- если Node доступен: `node --check app/web/app.js`;
- build onefile exe через `.\build.ps1`;
- upload artifact `ChatGPTSessionManager-windows-x64-dev.exe`.

Важно: artifact из CI не считать стабильным релизом.

## Этап 4. Release workflow

Создать `.github/workflows/release.yml`.

Триггер:

```yaml
on:
  push:
    tags:
      - "v*"
```

Поведение:

- собрать Windows exe на `windows-latest`;
- переименовать:

```text
ChatGPTSessionManager-windows-x64.exe
```

- посчитать SHA256:

```powershell
Get-FileHash .\dist\ChatGPTSessionManager.exe -Algorithm SHA256
```

- создать `.sha256` файл;
- создать GitHub Release;
- приложить `.exe` и `.sha256`.

Для создания release использовать официальный GitHub token через `GITHUB_TOKEN`.

## Этап 5. Проверка обновлений в приложении

Добавить backend-модуль:

```text
app/update_checker.py
```

Функции:

- получить текущую версию из `app/version.py`;
- запросить:

```text
https://api.github.com/repos/<owner>/<repo>/releases/latest
```

- прочитать `tag_name`;
- сравнить semver с текущей версией;
- найти asset для текущей платформы:

```text
ChatGPTSessionManager-windows-x64.exe
```

- вернуть в UI:

```json
{
  "current_version": "0.1.0",
  "latest_version": "0.2.0",
  "has_update": true,
  "release_url": "...",
  "asset_url": "...",
  "body": "release notes"
}
```

Добавить API методы в `app/api.py`:

- `check_for_updates()`;
- `open_latest_release()`;
- позднее `download_update()`.

Ошибки писать в `app.log`.

## Этап 6. UI обновлений

Добавить в левое меню пункт:

```text
Обновления
```

На странице показывать:

- текущая версия;
- последняя версия;
- статус: актуально / доступно обновление / ошибка проверки;
- release notes;
- кнопка `Проверить`;
- кнопка `Открыть релиз`;
- позднее кнопка `Скачать обновление`.

Также при запуске приложения:

- один раз в фоне проверить обновления;
- если обновление найдено, показать ненавязчивый toast/modal;
- не блокировать основной UI.

## Этап 7. Скачивание обновления

Добавить метод:

```python
download_update(asset_url: str) -> dict
```

Поведение:

- скачать `.exe` во временную папку:

```text
%TEMP%\ChatGPTSessionManager\updates\
```

- скачать `.sha256`;
- проверить SHA256;
- если checksum совпал, показать пользователю путь и кнопку `Открыть файл`.

На этом этапе не заменять текущий `.exe` автоматически.

## Этап 8. Полный self-update через updater.exe

Реализовать только после стабильной работы этапа 7.

Нужно отдельное приложение:

```text
updater/
  updater.py
```

Логика:

- основное приложение скачивает новый exe;
- запускает `updater.exe` с аргументами:

```text
--pid <current_pid>
--source <downloaded_exe>
--target <current_exe>
```

- основное приложение закрывается;
- updater ждёт завершения PID;
- делает backup старого exe;
- заменяет файл;
- запускает новую версию;
- при ошибке восстанавливает backup.

Важно: на Windows нельзя надёжно перезаписать запущенный `.exe` из самого приложения.

## Этап 9. Будущая поддержка Linux/macOS

Пока в README указать как planned.

Для Linux отдельно изучить:

- pywebview backend зависимости;
- AppImage или zip/tar.gz формат;
- отдельный GitHub Actions job на `ubuntu-latest`;
- asset name:

```text
ChatGPTSessionManager-linux-x64.AppImage
```

Для macOS:

- сборка на `macos-latest`;
- `.app` или `.dmg`;
- notarization позже, если потребуется.

## Acceptance Criteria

- В репозиторий не попадают `.venv`, `dist`, `build`, `auth.json`, логи, профили.
- `README.md` понятен пользователю и maintainer.
- `python -m pytest -q` проходит локально и в GitHub Actions.
- Push в `main` создаёт CI artifact, но не создаёт GitHub Release.
- Tag `vX.Y.Z` создаёт GitHub Release с Windows exe и SHA256.
- В приложении видна текущая версия.
- Приложение умеет проверить Latest Release и показать, что доступно обновление.
- Ошибки проверки обновлений пишутся в `app.log`.
- Самообновление не скачивает исходники из git и не требует Python на компьютере пользователя.
