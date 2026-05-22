const state = {
  profiles: [],
  settings: null,
  search: "",
  renameId: null,
  deleteId: null,
  initialized: false,
  updateInfo: null,
  downloadedUpdatePath: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

document.addEventListener("DOMContentLoaded", () => {
  $("#addProfileBtn").addEventListener("click", () => openModal("addModal"));
  $("#emptyAddBtn").addEventListener("click", () => openModal("addModal"));
  $("#refreshListBtn").addEventListener("click", loadProfiles);
  $("#profilesNavBtn").addEventListener("click", showProfilesPage);
  $("#logsNavBtn").addEventListener("click", showLogsPage);
  $("#updatesNavBtn").addEventListener("click", showUpdatesPage);
  $("#refreshLogsBtn").addEventListener("click", loadLogs);
  $("#copyLogsBtn").addEventListener("click", copyLogs);
  $("#checkUpdatesBtn").addEventListener("click", () => checkForUpdates(false));
  $("#openReleaseBtn").addEventListener("click", openLatestRelease);
  $("#downloadUpdateBtn").addEventListener("click", downloadUpdate);
  $("#openDownloadedBtn").addEventListener("click", openDownloadedUpdate);
  $("#installUpdateBtn").addEventListener("click", installUpdate);
  $("#profileSearch").addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderProfiles();
  });
  $("#manualAddBtn").addEventListener("click", () => {
    closeModals();
    openModal("manualModal");
  });
  $("#autoAddBtn").addEventListener("click", createAutoProfile);
  $("#chooseFileBtn").addEventListener("click", chooseJsonFile);
  $("#openSessionUrlBtn").addEventListener("click", openSessionUrl);
  $("#saveManualBtn").addEventListener("click", createManualProfile);
  $("#renameSaveBtn").addEventListener("click", saveRename);
  $("#deleteConfirmBtn").addEventListener("click", deleteProfile);
  $("#settingsBtn").addEventListener("click", openSettings);
  $("#settingsInlineBtn").addEventListener("click", openSettings);
  $("#settingsNavBtn").addEventListener("click", openSettings);
  $("#writeActiveBtn").addEventListener("click", writeActiveProfile);
  $("#openProfilesFolderBtn").addEventListener("click", openProfilesFolder);
  $("#openExportFileBtn").addEventListener("click", openExportFile);
  $("#chooseExportFileBtn").addEventListener("click", chooseExportFile);
  $("#resetExportPathBtn").addEventListener("click", resetExportPath);
  $("#saveExportPathBtn").addEventListener("click", saveExportPath);
  $("#modalBackdrop").addEventListener("click", closeModals);
  $$("[data-close-modal]").forEach((node) => node.addEventListener("click", closeModals));
  setupKeyboardShortcuts();
  setupJsonDrop();
  waitForApiAndLoad();
});

window.addEventListener("pywebviewready", () => {
  waitForApiAndLoad();
});

async function waitForApiAndLoad() {
  if (state.initialized) {
    return;
  }
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (window.pywebview && window.pywebview.api) {
      state.initialized = true;
      await loadAppInfo();
      await loadProfiles();
      checkForUpdates(true);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  showAlert("Не удалось подключиться к API приложения. Перезапустите приложение.", "danger");
}

async function loadAppInfo() {
  const result = await window.pywebview.api.get_app_info();
  if (result.ok) {
    $("#appVersion").textContent = `v${result.version}`;
  }
}

async function loadProfiles() {
  const result = await window.pywebview.api.list_profiles();
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  state.profiles = result.profiles;
  state.settings = result.settings;
  $("#storagePath").textContent = `Папка профилей: ${result.storage_path}`;
  $("#exportPath").textContent = result.settings.export_path;
  $("#writeActiveBtn").disabled = !result.settings.selected_profile_id;
  renderProfiles();
}

function renderProfiles() {
  const table = $("#profilesTable");
  const filtered = state.profiles.filter((profile) => {
    if (!state.search) return true;
    return `${profile.name} ${profile.expires} ${profile.last_refresh}`.toLowerCase().includes(state.search);
  });
  table.innerHTML = "";
  $("#emptyState").classList.toggle("d-none", state.profiles.length > 0);
  $("#profilesTable").classList.toggle("d-none", state.profiles.length === 0);
  $("#profilesSummary").textContent = `${state.profiles.length} сохранено, ${state.profiles.filter((item) => item.is_active).length} активно`;
  $("#profilesCount").textContent = `${filtered.length} из ${state.profiles.length} профилей`;

  if (state.profiles.length > 0) {
    const header = document.createElement("div");
    header.className = "table-row table-header";
    header.innerHTML = `
      <div>Профиль</div>
      <div>Обновлён</div>
      <div>Истекает</div>
      <div>Статус</div>
      <div></div>
    `;
    table.appendChild(header);
  }

  filtered.forEach((profile) => {
    const row = document.createElement("article");
    row.className = "table-row profile-row";
    const active = Boolean(profile.is_active);
    const selected = state.settings && state.settings.selected_profile_id === profile.id;
    if (selected) {
      row.classList.add("profile-row-selected");
    }
    row.innerHTML = `
      <div class="profile-name-cell">
        <span class="file-icon">◇</span>
        <span class="profile-name">${escapeHtml(profile.name)}</span>
      </div>
      <div class="muted">${formatDate(profile.last_refresh)}</div>
      <div class="${active ? "muted" : "status-expired"}">${active ? formatDate(profile.expires) : "Истёк"}</div>
      <div>
        <div class="status ${active ? "status-active" : "status-expired"}">
          <span class="status-dot"></span>
          <span>${active ? "Активен" : "Истёк"}</span>
        </div>
      </div>
      <div class="profile-actions">
        <button class="btn btn-outline-secondary icon-action action-inline" data-action="activate" ${active ? "" : "disabled"} title="${selected ? "Уже активный" : "Сделать активным и записать файл"}">★</button>
        <button class="btn btn-outline-secondary icon-action action-inline" data-action="refresh" title="Обновить">↻</button>
        <button class="btn btn-outline-secondary icon-action action-inline" data-action="rename" title="Переименовать">✎</button>
        <button class="btn btn-danger icon-action action-inline" data-action="delete" title="Удалить">🗑</button>
        <button class="btn btn-outline-secondary icon-action action-menu-button" data-menu-toggle title="Действия">⋯</button>
      </div>
    `;
    row.querySelector("[data-action='activate']").addEventListener("click", () => activateProfile(profile.id));
    row.querySelector("[data-action='refresh']").addEventListener("click", () => refreshProfile(profile.id));
    row.querySelector("[data-action='rename']").addEventListener("click", () => openRename(profile));
    row.querySelector("[data-action='delete']").addEventListener("click", () => openDelete(profile));
    row.querySelector("[data-menu-toggle]").addEventListener("click", (event) => openActionMenu(event, profile));
    table.appendChild(row);
  });

  if (state.profiles.length > 0 && filtered.length === 0) {
    const emptySearch = document.createElement("div");
    emptySearch.className = "empty-search";
    emptySearch.textContent = "По этому запросу профили не найдены.";
    table.appendChild(emptySearch);
  }
}

document.addEventListener("click", (event) => {
  if (!event.target.closest("#floatingActionDropdown") && !event.target.closest("[data-menu-toggle]")) {
    closeActionMenus();
  }
});

window.addEventListener("resize", closeActionMenus);
window.addEventListener("scroll", closeActionMenus, true);

function openActionMenu(event, profile) {
  event.stopPropagation();
  const dropdown = $("#floatingActionDropdown");
  const button = event.currentTarget;
  const rect = button.getBoundingClientRect();
  const active = Boolean(profile.is_active);
  dropdown.innerHTML = `
    <button data-floating-action="activate" ${active ? "" : "disabled"}>★ Сделать активным</button>
    <button data-floating-action="refresh">↻ Обновить</button>
    <button data-floating-action="rename">✎ Переименовать</button>
    <button class="danger-item" data-floating-action="delete">🗑 Удалить</button>
  `;
  dropdown.querySelector("[data-floating-action='activate']").addEventListener("click", () => {
    closeActionMenus();
    activateProfile(profile.id);
  });
  dropdown.querySelector("[data-floating-action='refresh']").addEventListener("click", () => {
    closeActionMenus();
    refreshProfile(profile.id);
  });
  dropdown.querySelector("[data-floating-action='rename']").addEventListener("click", () => {
    closeActionMenus();
    openRename(profile);
  });
  dropdown.querySelector("[data-floating-action='delete']").addEventListener("click", () => {
    closeActionMenus();
    openDelete(profile);
  });
  dropdown.classList.remove("d-none");

  const dropdownWidth = dropdown.offsetWidth || 210;
  const left = Math.max(12, Math.min(rect.right - dropdownWidth, window.innerWidth - dropdownWidth - 12));
  const top = Math.min(rect.bottom + 6, window.innerHeight - dropdown.offsetHeight - 12);
  dropdown.style.left = `${left}px`;
  dropdown.style.top = `${Math.max(12, top)}px`;
}

function closeActionMenus() {
  const dropdown = $("#floatingActionDropdown");
  if (dropdown) {
    dropdown.classList.add("d-none");
  }
}

function showProfilesPage() {
  $("#profilesPage").classList.remove("d-none");
  $("#logsPage").classList.add("d-none");
  $("#updatesPage").classList.add("d-none");
  $("#profilesNavBtn").classList.add("active");
  $("#logsNavBtn").classList.remove("active");
  $("#updatesNavBtn").classList.remove("active");
  $(".breadcrumb").textContent = "Профили";
}

async function showLogsPage() {
  $("#profilesPage").classList.add("d-none");
  $("#logsPage").classList.remove("d-none");
  $("#updatesPage").classList.add("d-none");
  $("#profilesNavBtn").classList.remove("active");
  $("#logsNavBtn").classList.add("active");
  $("#updatesNavBtn").classList.remove("active");
  $(".breadcrumb").textContent = "Логи";
  await loadLogs();
}

async function showUpdatesPage() {
  $("#profilesPage").classList.add("d-none");
  $("#logsPage").classList.add("d-none");
  $("#updatesPage").classList.remove("d-none");
  $("#profilesNavBtn").classList.remove("active");
  $("#logsNavBtn").classList.remove("active");
  $("#updatesNavBtn").classList.add("active");
  $(".breadcrumb").textContent = "Обновления";
  if (!state.updateInfo) {
    await checkForUpdates(false);
  }
}

async function loadLogs() {
  const result = await window.pywebview.api.read_logs();
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  $("#logsPath").textContent = result.path;
  $("#logsViewer").textContent = result.content || "Лог-файл пуст.";
}

async function copyLogs() {
  const text = $("#logsViewer").textContent;
  try {
    await navigator.clipboard.writeText(text);
    showAlert("Логи скопированы.", "success");
  } catch (error) {
    showAlert("Не удалось скопировать логи. Выделите текст вручную.", "warning");
  }
}

async function checkForUpdates(silent) {
  setUpdateStatus("checking", "Проверка...");
  const result = await window.pywebview.api.check_for_updates();
  if (!result.ok) {
    setUpdateStatus("error", "Ошибка проверки");
    $("#updatesSummary").textContent = result.error || "Не удалось проверить обновления.";
    $("#releaseNotes").textContent = result.error || "";
    if (!silent) {
      showAlert(result.error || "Не удалось проверить обновления.", "danger");
    }
    return;
  }
  state.updateInfo = result;
  $("#currentVersion").textContent = `v${result.current_version}`;
  $("#latestVersion").textContent = `v${result.latest_version}`;
  $("#releaseNotes").textContent = result.body || "Release notes отсутствуют.";
  $("#updatesSummary").textContent = result.release_url || "GitHub Releases";
  $("#downloadUpdateBtn").disabled = !result.has_update || !result.asset_url;
  setUpdateStatus(result.has_update ? "available" : "current", result.has_update ? "Доступно обновление" : "Актуально");
  if (silent && result.has_update) {
    showAlert(`Доступна новая версия v${result.latest_version}.`, "info");
  }
}

function setUpdateStatus(kind, text) {
  const status = $("#updateStatus");
  status.className = `status update-status update-${kind}`;
  status.innerHTML = `<span class="status-dot"></span><span>${escapeHtml(text)}</span>`;
}

async function openLatestRelease() {
  const result = await window.pywebview.api.open_latest_release();
  if (!result.ok) {
    showAlert(result.error, "danger");
  }
}

async function downloadUpdate() {
  if (!state.updateInfo || !state.updateInfo.asset_url) {
    showAlert("Asset обновления не найден.", "warning");
    return;
  }
  $("#downloadUpdateBtn").disabled = true;
  $("#downloadUpdateBtn").textContent = "Скачивание...";
  const result = await window.pywebview.api.download_update(state.updateInfo.asset_url);
  $("#downloadUpdateBtn").textContent = "Скачать обновление";
  $("#downloadUpdateBtn").disabled = false;
  if (!result.ok) {
    showAlert(result.error || "Не удалось скачать обновление.", "danger");
    return;
  }
  state.downloadedUpdatePath = result.path;
  $("#downloadPath").textContent = result.path;
  $("#downloadResult").classList.remove("d-none");
  showAlert(`Обновление скачано и проверено: ${result.path}`, "success");
}

async function openDownloadedUpdate() {
  if (!state.downloadedUpdatePath) return;
  const result = await window.pywebview.api.open_downloaded_update(state.downloadedUpdatePath);
  if (!result.ok) {
    showAlert(result.error, "danger");
  }
}

async function installUpdate() {
  if (!state.downloadedUpdatePath) return;
  const result = await window.pywebview.api.install_update(state.downloadedUpdatePath);
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  showAlert("Установка запущена. Приложение закроется.", "info");
}

async function createAutoProfile() {
  closeModals();
  showAlert("Откроется окно входа ChatGPT. После успешного входа приложение попробует получить сессию.", "info");
  const result = await window.pywebview.api.create_auto_profile();
  handleProfileMutation(result, "Профиль добавлен.");
}

async function refreshProfile(profileId) {
  showAlert("Откроется окно входа ChatGPT для обновления сессии.", "info");
  const result = await window.pywebview.api.refresh_profile(profileId);
  const message = result.synced_path ? `Профиль обновлён. Файл перезаписан: ${result.synced_path}` : "Профиль обновлён.";
  handleProfileMutation(result, message);
}

async function createManualProfile() {
  const rawJson = $("#manualJson").value.trim();
  if (!rawJson) {
    showAlert("Вставьте JSON или выберите файл.", "warning");
    return;
  }
  const result = await window.pywebview.api.create_manual_profile(rawJson);
  if (result.ok) {
    $("#manualJson").value = "";
    closeModals();
  }
  handleProfileMutation(result, "Профиль добавлен.");
}

async function chooseJsonFile() {
  const result = await window.pywebview.api.read_json_file();
  if (!result.ok) {
    showAlert(result.error, "warning");
    return;
  }
  $("#manualJson").value = result.content;
  showAlert(`Загружен файл: ${result.path}`, "success");
}

async function openSessionUrl() {
  const result = await window.pywebview.api.open_session_url();
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  showAlert("Страница открыта в стандартном браузере.", "success");
}

function openRename(profile) {
  state.renameId = profile.id;
  $("#renameInput").value = profile.name;
  openModal("renameModal");
  $("#renameInput").focus();
}

async function saveRename() {
  const result = await window.pywebview.api.rename_profile(state.renameId, $("#renameInput").value);
  if (result.ok) {
    closeModals();
  }
  handleProfileMutation(result, "Профиль переименован.");
}

function openDelete(profile) {
  state.deleteId = profile.id;
  $("#deleteText").textContent = `Удалить профиль «${profile.name}»? Это действие нельзя отменить.`;
  openModal("deleteModal");
}

async function deleteProfile() {
  const result = await window.pywebview.api.delete_profile(state.deleteId);
  if (result.ok) {
    closeModals();
    await loadProfiles();
    showAlert("Профиль удалён.", "success");
    return;
  }
  showAlert(result.error, "danger");
}

async function activateProfile(profileId) {
  const result = await window.pywebview.api.activate_profile(profileId);
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  await loadProfiles();
  showAlert(formatWriteMessage(`Активный профиль выбран. Файл перезаписан: ${result.path}`, result.backup_path), "success");
}

async function writeActiveProfile() {
  const result = await window.pywebview.api.write_active_profile();
  if (!result.ok) {
    await loadProfiles();
    showAlert(result.error, "warning");
    return;
  }
  showAlert(formatWriteMessage(`Файл перезаписан: ${result.path}`, result.backup_path), "success");
}

function openSettings() {
  $("#exportPathInput").value = state.settings ? state.settings.export_path : "";
  renderRecentExports();
  openModal("settingsModal");
}

function renderRecentExports() {
  const host = $("#recentExports");
  const paths = state.settings && Array.isArray(state.settings.recent_export_paths) ? state.settings.recent_export_paths : [];
  host.innerHTML = "";
  if (paths.length === 0) return;
  const label = document.createElement("div");
  label.className = "panel-label recent-label";
  label.textContent = "Недавние пути";
  host.appendChild(label);
  paths.forEach((path) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "recent-export-item";
    button.textContent = path;
    button.addEventListener("click", () => {
      $("#exportPathInput").value = path;
    });
    host.appendChild(button);
  });
}

async function chooseExportFile() {
  const result = await window.pywebview.api.choose_export_file();
  if (!result.ok) {
    showAlert(result.error, "warning");
    return;
  }
  closeModals();
  await loadProfiles();
  showAlert(formatWriteMessage(result.synced_path ? `Путь сохранён. Файл перезаписан: ${result.synced_path}` : "Путь сохранён.", result.backup_path), "success");
}

async function saveExportPath() {
  const result = await window.pywebview.api.set_export_path($("#exportPathInput").value.trim());
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  closeModals();
  await loadProfiles();
  showAlert(formatWriteMessage(result.synced_path ? `Путь сохранён. Файл перезаписан: ${result.synced_path}` : "Путь сохранён.", result.backup_path), "success");
}

async function resetExportPath() {
  const result = await window.pywebview.api.reset_export_path();
  if (!result.ok) {
    showAlert(result.error, "danger");
    return;
  }
  closeModals();
  await loadProfiles();
  showAlert(formatWriteMessage(result.synced_path ? `Путь по умолчанию восстановлен. Файл перезаписан: ${result.synced_path}` : "Путь по умолчанию восстановлен.", result.backup_path), "success");
}

async function handleProfileMutation(result, successMessage) {
  if (!result.ok) {
    showAlert(result.error || "Операция не выполнена.", "danger");
    return;
  }
  await loadProfiles();
  showAlert(successMessage, "success");
}

function openModal(id) {
  closeActionMenus();
  $("#modalBackdrop").classList.remove("d-none");
  $("#" + id).classList.remove("d-none");
}

function closeModals() {
  $("#modalBackdrop").classList.add("d-none");
  $$(".modal-panel").forEach((node) => node.classList.add("d-none"));
  state.renameId = null;
  state.deleteId = null;
}

function showAlert(message, type = "info") {
  const host = $("#alertHost");
  const alert = document.createElement("div");
  alert.className = `alert alert-${type}`;
  alert.textContent = message;
  host.appendChild(alert);
  setTimeout(() => alert.remove(), 7000);
}

async function openProfilesFolder() {
  const result = await window.pywebview.api.open_profiles_folder();
  if (!result.ok) {
    showAlert(result.error, "danger");
  }
}

async function openExportFile() {
  const result = await window.pywebview.api.open_export_file();
  if (!result.ok) {
    showAlert(result.error, "danger");
  }
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      writeActiveProfile();
    }
  });
}

function setupJsonDrop() {
  const overlay = $("#dropOverlay");
  window.addEventListener("dragover", (event) => {
    event.preventDefault();
    overlay.classList.remove("d-none");
  });
  window.addEventListener("dragleave", (event) => {
    if (event.clientX <= 0 || event.clientY <= 0 || event.clientX >= window.innerWidth || event.clientY >= window.innerHeight) {
      overlay.classList.add("d-none");
    }
  });
  window.addEventListener("drop", async (event) => {
    event.preventDefault();
    overlay.classList.add("d-none");
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".json")) {
      showAlert("Перетащите JSON-файл.", "warning");
      return;
    }
    const content = await file.text();
    $("#manualJson").value = content;
    closeModals();
    openModal("manualModal");
    showAlert(`JSON загружен: ${file.name}`, "success");
  });
}

function formatWriteMessage(message, backupPath) {
  return backupPath ? `${message}. Backup: ${backupPath}` : message;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}
