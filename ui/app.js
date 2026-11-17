/* Cosmic Optimizer — frontend. Все данные приходят из window.pywebview.api. */
(() => {
  "use strict";

  const state = {
    view: "dashboard",
    admin: false,
    system: null,
    paths: {},
    categories: [],
    tweaks: [],
    category: "performance",
    search: "",
    onlyOn: false,
    pending: new Map(),
    busyMode: new Map(),
    flash: new Map(),
    details: new Set(),
    devices: [],
    scripts: [],
    tools: [],
    toolsGroup: "all",
    gpu: [],
    backups: [],
    settings: {},
    profilePreview: null,
    telemetry: null,
  };

  const TITLES = {
    dashboard: ["Главная", "Состояние системы и последние действия"],
    registry: ["Реестр", "Проверенные настройки Windows по категориям"],
    telemetry: ["Телеметрия", "Windows, Microsoft и браузеры в одном профиле"],
    power: ["Электропитание", "Схемы электропитания Windows"],
    devices: ["Видеокарта и устройства", "Включение и отключение PnP-устройств"],
    maintenance: ["Обслуживание", "Очистка мусора, диски, проверки и замеры"],
    benchmark: ["Бенчмарк", "Короткий контролируемый тест накопителя"],
    scripts: ["Мои скрипты", "Все файлы из исходного набора: запуск и откат"],
    tools: ["Инструменты", "Скачивание, туториалы и настройки под ваше железо"],
    backups: ["Бэкапы и восстановление", "Точки отката реестра и состояния"],
    logs: ["Логи", "Журнал действий приложения"],
    settings: ["Настройки", "Поведение и расположение данных"],
  };

  const DIAGNOSTICS = [
    {
      id: "startup", title: "Долгая загрузка",
      heading: "Проверим время загрузки и автозапуск",
      description: "Прочитаем последний замер Windows из журнала диагностики и посчитаем записи автозапуска. Проверка сохранит снимок в истории «до / после», но ничего в системе не поменяет.",
      steps: ["Время загрузки берётся из последнего доступного события Windows; после недавней переустановки или очистки журнала данных может не быть.", "Число записей автозапуска — это количество найденных команд, а не оценка их влияния на загрузку."],
      action: "startup", button: "Снять замер"
    },
    {
      id: "stutter", title: "Микрофризы / тормоза",
      heading: "Посмотрим нагрузку ресурсов сейчас",
      description: "В течение нескольких секунд снимем CPU и память. Запустите проверку, пока проблема проявляется: замер в простое не покажет игровую нагрузку.",
      steps: ["Высокая загрузка CPU или почти занятая память могут указывать на нехватку ресурсов в момент замера.", "Это короткий снимок, а не тест FPS, времени кадра или задержки ввода."],
      action: "stutter", button: "Начать замер"
    },
    {
      id: "ping", title: "Высокий ping",
      heading: "Измерим ответ выбранного сервера",
      description: "Отправим четыре стандартных ICMP-запроса на указанный вами адрес или сервер. Это проверяет сетевой путь до этой цели; игровой сервер может иметь другой маршрут.",
      steps: ["Потери и скачки задержки важнее одного удачного ответа.", "Если сервер не отвечает, он или сеть могут блокировать ICMP — это само по себе не доказывает, что сервер игры недоступен."],
      action: "ping", button: "Проверить"
    },
    {
      id: "thermal", title: "Высокая температура",
      heading: "Проверим доступный температурный датчик",
      description: "Покажем значение датчика, который Windows предоставляет через ACPI. На некоторых ПК этот датчик отсутствует или не является датчиком CPU/GPU.",
      steps: ["Сверьте показатель с температурой в фирменной утилите производителя процессора или видеокарты.", "Одного снимка недостаточно, чтобы подтвердить перегрев или троттлинг."],
      action: "thermal", button: "Считать датчик"
    },
    {
      id: "disk", title: "Диск / мало места",
      heading: "Проверим состояние накопителей и свободное место",
      description: "Прочитаем доступные сведения SMART и заполненность томов. Ничего не удаляется и не исправляется.",
      steps: ["Состояние и температура могут быть недоступны, если накопитель или драйвер не отдают эти данные Windows.", "Мало свободного места может мешать обновлениям и работе приложений, но не всегда является причиной тормозов."],
      action: "disk", button: "Проверить диски"
    },
    {
      id: "windows", title: "Ошибки Windows",
      heading: "Откроем встроенные проверки Windows",
      description: "SFC проверяет системные файлы, DISM восстанавливает хранилище компонентов. Это ремонтные операции, поэтому мастер не запускает их сам.",
      steps: ["Сначала обычно запускают SFC. Если он сообщает, что не смог исправить файлы, можно выполнить DISM, а затем снова SFC.", "Команды требуют прав администратора и могут выполняться долго."],
      action: "windows", button: "К проверкам SFC / DISM"
    },
  ];

  const $ = (sel) => document.querySelector(sel);

  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));

  const fmtDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return esc(iso);
    return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  /* ---------- мост ---------- */
  async function api(method, ...args) {
    if (!window.pywebview || !window.pywebview.api) throw new Error("Мост Python недоступен");
    const fn = window.pywebview.api[method];
    if (typeof fn !== "function") throw new Error(`Метод API не найден: ${method}`);
    const res = await fn(...args);
    if (!res || res.ok !== true) throw new Error((res && res.error) || "Неизвестная ошибка");
    return res.data;
  }

  let busyCount = 0;
  let busyClock = null;
  let busyStartedAt = 0;

  function elapsedLabel(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const minutes = Math.floor(total / 60);
    const remainder = total % 60;
    return minutes ? `${minutes} мин ${String(remainder).padStart(2, "0")} с` : `${remainder} с`;
  }

  function busy(text) {
    busyCount += 1;
    $("#loading-text").textContent = text || "Выполняется…";
    $("#loading").classList.remove("hidden");
    if (busyCount === 1) {
      busyStartedAt = Date.now();
      $("#loading-elapsed").textContent = "Подготовка…";
      $("#loading-detail").textContent = "Ожидание ответа от приложения";
      $("#loading-track").classList.add("is-indeterminate");
      $("#loading-progress").style.width = "34%";
      busyClock = setInterval(() => {
        $("#loading-elapsed").textContent = `Прошло ${elapsedLabel((Date.now() - busyStartedAt) / 1000)}`;
      }, 1000);
    }
  }

  function updateBusyProgress(detail, percent = null, subtitle = null) {
    if (detail) $("#loading-detail").textContent = detail;
    if (subtitle) $("#loading-elapsed").textContent = subtitle;
    const track = $("#loading-track");
    const bar = $("#loading-progress");
    if (percent !== null && percent !== undefined && Number.isFinite(Number(percent))) {
      track.classList.remove("is-indeterminate");
      bar.style.width = `${Math.max(0, Math.min(100, Number(percent)))}%`;
    } else {
      track.classList.add("is-indeterminate");
      bar.style.width = "34%";
    }
  }

  function idle() {
    busyCount = Math.max(0, busyCount - 1);
    if (busyCount === 0) {
      $("#loading").classList.add("hidden");
      if (busyClock) clearInterval(busyClock);
      busyClock = null;
    }
  }

  async function run(text, fn) {
    busy(text);
    try {
      return await fn();
    } catch (err) {
      toast(err.message || String(err), true);
      return null;
    } finally {
      idle();
    }
  }

  function toast(message, isError = false) {
    const node = document.createElement("div");
    node.className = "toast" + (isError ? " error" : "");
    node.textContent = message;
    $("#toast-wrap").appendChild(node);
    setTimeout(() => {
      node.style.opacity = "0";
      node.style.transition = "opacity .25s ease";
      setTimeout(() => node.remove(), 260);
    }, isError ? 6500 : 3800);
  }

  /* ---------- модалка ---------- */
  let modalResolve = null;
  function confirmAction(title, text, okLabel = "Подтвердить", force = false) {
    if (!force && !state.settings.confirmations) return Promise.resolve(true);
    $("#modal-title").textContent = title;
    $("#modal-text").textContent = text;
    $("#modal-ok").textContent = okLabel;
    $("#modal").classList.remove("hidden");
    $("#modal-ok").focus();
    return new Promise((resolve) => { modalResolve = resolve; });
  }
  function closeModal(result) {
    $("#modal").classList.add("hidden");
    $("#profile-restore-remember").classList.add("hidden");
    $("#modal-skip").classList.add("hidden");
    $("#modal-cancel").textContent = "Отмена";
    $("#modal-ok").textContent = "Подтвердить";
    if (modalResolve) { modalResolve(result); modalResolve = null; }
  }
  $("#modal-cancel").addEventListener("click", () => closeModal(false));
  $("#modal-ok").addEventListener("click", () => closeModal(true));
  $("#modal-skip").addEventListener("click", () => closeModal("skip"));
  $("#modal").addEventListener("click", (e) => { if (e.target === $("#modal")) closeModal(false); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#modal").classList.contains("hidden")) closeModal(false);
  });

  /* ---------- навигация ---------- */
  function setView(view) {
    if (view === "optimization") {
      const submenu = document.getElementById("optimization-subnav");
      const trigger = document.querySelector('[data-view="optimization"]');
      const open = submenu.hidden;
      submenu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      return;
    }
    if (!TITLES[view]) return;
    state.view = view;
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.view === view);
    });
    document.querySelectorAll(".view").forEach((node) => {
      node.classList.toggle("is-active", node.id === `view-${view}`);
    });
    document.querySelectorAll(".nav-subitem").forEach((btn) => btn.classList.toggle("is-active", btn.dataset.view === view));
    const optimizationView = ["power", "telemetry", "registry", "scripts", "tools"].includes(view);
    const submenu = document.getElementById("optimization-subnav");
    const trigger = document.querySelector('[data-view="optimization"]');
    submenu.hidden = !optimizationView;
    trigger.setAttribute("aria-expanded", String(optimizationView));
    trigger.classList.toggle("is-active", optimizationView);
    $("#section-title").textContent = TITLES[view][0];
    $("#section-sub").textContent = TITLES[view][1];
    $("#content").scrollTop = 0;
    if (view === "dashboard") startMonitor();
    else stopMonitor();
    showSkeleton(view);
    loadView(view);
  }

  function loadView(view) {
    const loaders = {
      dashboard: loadDashboard,
      registry: loadRegistry,
      telemetry: loadTelemetry,
      power: loadPower,
      devices: loadDevices,
      maintenance: loadMaintenance,
      benchmark: loadBenchmark,
      scripts: loadScripts,
      tools: loadTools,
      backups: loadBackups,
      logs: loadLogs,
      settings: loadSettings,
    };
    if (loaders[view]) loaders[view]();
  }

  async function loadPower() {
    const data = await run("Чтение схем электропитания…", () => api("power_schemes"));
    if (!data) return;
    const box = $("#power-schemes");
    box.innerHTML = (data.schemes || []).map((scheme) => `
      <article class="power-scheme ${scheme.active ? "is-active" : ""}">
        <div class="power-scheme-copy"><strong>${esc(scheme.name)}</strong><small class="muted">${scheme.active ? "Используется сейчас" : scheme.builtin ? "Встроенная схема Windows" : "Пользовательская схема"}</small><code>${esc(scheme.guid)}</code></div>
        <div class="power-scheme-actions">${scheme.active ? '<span class="badge badge-ok">Активна</span>' : `<button class="btn btn-ghost" data-power-activate="${esc(scheme.guid)}">Включить</button>`}${scheme.deletable ? `<button class="btn btn-danger" data-power-delete="${esc(scheme.guid)}">Удалить схему</button>` : ""}</div>
      </article>`).join("") || '<p class="muted">Windows не вернула схем электропитания.</p>';
  }
  $("#btn-refresh-power").addEventListener("click", loadPower);
  $("#power-schemes").addEventListener("click", async (event) => {
    const activate = event.target.closest("[data-power-activate]");
    const remove = event.target.closest("[data-power-delete]");
    if (!activate && !remove) return;
    const guid = (activate || remove).dataset.powerActivate || (activate || remove).dataset.powerDelete;
    if (activate) {
      const ok = await confirmAction("Включить схему?", "Windows переключится на выбранную схему электропитания.", "Включить");
      if (!ok) return;
      const result = await run("Переключение электропитания…", () => api("activate_power_scheme", guid));
      if (result) { toast("Схема электропитания включена"); loadPower(); }
    } else {
      const ok = await confirmAction("Удалить пользовательскую схему?", "Схема будет удалена из Windows без возможности восстановления. Встроенные и активные схемы защищены.", "Удалить", true);
      if (!ok) return;
      const result = await run("Удаление схемы…", () => api("delete_power_scheme", guid));
      if (result) { toast("Схема удалена"); loadPower(); }
    }
  });

  document.getElementById("nav").addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-item, .nav-subitem");
    if (btn) setView(btn.dataset.view);
  });
  document.addEventListener("click", (e) => {
    const goto = e.target.closest("[data-goto]");
    if (goto) setView(goto.dataset.goto);
  });

  /* ---------- обзор ---------- */
  async function loadDashboard() {
    const data = await run("Чтение состояния системы…", () => api("get_dashboard"));
    if (!data) return;
    state.system = data.system;
    state.admin = data.system.admin;
    state.paths = data.paths;
    state.settings = data.settings;
    $("#btn-reset-profile-restore-choice").disabled = data.settings.profile_restore_point == null;

    renderAdmin(data.system.admin);
    $("#side-version").textContent = `v${data.system.app_version}`;

    const sys = data.system;
    $("#sys-cards").innerHTML = `
      <div class="stat">
        <div class="stat-label">Windows</div>
        <div class="stat-value">${esc(sys.edition || sys.os || "Windows")}</div>
        <div class="stat-sub">Версия ${esc(sys.version || "—")} · сборка ${esc(sys.build || "—")} · ${esc(sys.arch || "")}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Компьютер</div>
        <div class="stat-value">${esc(sys.hostname)}</div>
        <div class="stat-sub">Пользователь: ${esc(sys.user || "—")}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Права</div>
        <div class="stat-value">${sys.admin ? "Администратор" : "Обычный пользователь"}</div>
        <div class="stat-sub">Твиков в каталоге: ${esc(data.tweaks_total)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Твики сейчас</div>
        <div class="stat-value">Включено ${esc(data.tweaks_on)} из ${esc(data.tweaks_total)}</div>
        <div class="stat-sub">${data.tweaks_on ? esc((data.tweaks_on_names || []).slice(0, 3).join(", ")) + (data.tweaks_on > 3 ? ` и ещё ${data.tweaks_on - 3}` : "") : "Ни одна настройка не изменена"}</div>
      </div>`;

  }

  function renderAdmin(isAdmin) {
    const badge = $("#admin-badge");
    badge.textContent = isAdmin ? "Администратор" : "Без прав администратора";
    badge.className = "badge " + (isAdmin ? "badge-ok badge-dot" : "badge-warn");
    $("#admin-banner").classList.toggle("hidden", isAdmin);
  }

  $("#btn-elevate").addEventListener("click", async () => {
    await run("Запрос прав администратора…", async () => {
      await api("restart_as_admin");
      toast("Подтвердите запрос UAC. Текущее окно можно закрыть.");
      return true;
    });
  });

  $("#btn-undo").addEventListener("click", async () => {
    const ok = await confirmAction("Отменить последнее действие?", "Последний применённый или откаченный твик вернётся в предыдущее состояние.", "Отменить действие");
    if (!ok) return;
    const res = await run("Откат…", () => api("undo_last"));
    if (res) { toast(res.message); if (state.view === "dashboard") loadDashboard(); }
  });

  /* ---------- реестр ---------- */
  async function loadRegistry() {
    const data = await run("Загрузка каталога твиков…", () => api("list_tweaks"));
    if (!data) return;
    state.categories = data.categories;
    state.tweaks = data.tweaks;
    state.admin = data.admin;
    renderAdmin(data.admin);
    if (!state.categories.some((c) => c.id === state.category)) state.category = state.categories[0]?.id || "performance";
    renderChips();
    renderTweaks();
  }

  async function loadTelemetry() {
    const data = await run("Чтение политик телеметрии…", () => api("get_telemetry_status"));
    if (!data) return;
    state.telemetry = data;
    renderTelemetry(data);
  }

  function renderTelemetry(data) {
    const controls = data.controls || [];
    const groups = data.groups || [{ id: "windows", name: "Настройки" }];
    const available = controls.filter((item) => item.available);
    const minimized = available.filter((item) => item.minimized).length;
    const managed = controls.filter((item) => item.managed).length;
    const hasAdminManaged = controls.some((item) => item.managed && item.requires_admin);

    $("#telemetry-intro").textContent = `${data.edition || "Windows"} · сборка ${data.build || "—"}. Ограничено ${minimized} из ${available.length} поддерживаемых параметров.`;
    $("#telemetry-count").textContent = `${minimized}/${available.length}`;
    $("#btn-telemetry-apply").disabled = !data.admin;
    $("#btn-telemetry-apply").title = data.admin ? "Сохранит исходные значения и активирует все доступные ограничения" : "Для системных политик запустите приложение от администратора";
    $("#btn-telemetry-restore").disabled = managed === 0 || (!data.admin && hasAdminManaged);
    $("#btn-telemetry-restore").title = !data.admin && hasAdminManaged ? "Для восстановления системных политик нужны права администратора" : "Восстановить значения, сохранённые перед первым применением";

    const renderControl = (item) => {
      let actionLabel = "Ограничить";
      let actionKind = "apply";
      let disabled = !item.available || (item.requires_admin && !data.admin);
      let stateLabel = item.state_label;
      let stateClass = item.minimized ? "badge-ok" : "badge-muted";
      if (item.managed) {
        actionLabel = "Восстановить";
        actionKind = "restore";
        disabled = item.requires_admin && !data.admin;
        stateLabel = "Изменено приложением · " + stateLabel;
      } else if (!item.available) {
        actionLabel = "Недоступно";
        stateLabel = item.unavailable_reason || "Не поддерживается";
      } else if (item.minimized) {
        actionLabel = "Уже активно";
        disabled = true;
        stateLabel = "Ограничение активно · " + stateLabel;
      } else if (item.requires_admin && !data.admin) {
        actionLabel = "Нужен администратор";
      }
      return `
        <article class="telemetry-row ${item.minimized ? "is-limited" : ""} ${!item.available ? "is-unavailable" : ""}">
          <div class="telemetry-row-copy">
            <div class="telemetry-row-heading"><h3>${esc(item.name)}</h3><span class="badge ${stateClass}">${esc(stateLabel)}</span></div>
            <p class="muted small">${esc(item.description)}</p>
          </div>
          <button class="btn btn-ghost telemetry-row-action" data-telemetry-id="${esc(item.id)}" data-telemetry-action="${actionKind}" ${disabled ? "disabled" : ""}>${esc(actionLabel)}</button>
        </article>`;
    };

    $("#telemetry-list").innerHTML = groups.map((group) => {
      const groupControls = controls.filter((item) => item.group === group.id);
      if (!groupControls.length) return "";
      const groupActive = groupControls.filter((item) => item.available && item.minimized).length;
      const groupAvailable = groupControls.filter((item) => item.available).length;
      return `
        <section class="telemetry-group" aria-labelledby="telemetry-group-${esc(group.id)}">
          <div class="telemetry-group-head">
            <h3 id="telemetry-group-${esc(group.id)}">${esc(group.name)}</h3>
            <span class="muted small">${groupActive}/${groupAvailable} активно</span>
          </div>
          <div class="telemetry-group-list">${groupControls.map(renderControl).join("")}</div>
        </section>`;
    }).join("");
  }

  async function applyTelemetryProfile() {
    const ok = await confirmAction(
      "Активировать все ограничения телеметрии?",
      "Сохранятся точные текущие значения, затем будут активированы доступные политики Windows, разрешений приложений, Microsoft Office, Edge, .NET CLI, PowerShell и установленных браузеров. Доступные задания совместимости и CEIP, а также служба диагностики DiagTrack будут отключены; это может ограничить Feedback Hub и часть средств диагностики. Ограничение доступа к камере, микрофону, местоположению и файлам влияет на соответствующие возможности приложений. Обязательные данные безопасности на обычных редакциях Windows, Defender и Windows Update останутся включены.",
      "Активировать все",
      true,
    );
    if (!ok) return;
    const result = await run("Применение политик приватности…", () => api("apply_telemetry_profile"));
    if (!result) return;
    state.telemetry = result.state;
    renderTelemetry(result.state);
    const availableIds = new Set((result.state?.controls || []).filter((item) => item.available).map((item) => item.id));
    const failed = (result.results || []).filter((item) => !item.ok && availableIds.has(item.id));
    toast(failed.length
      ? `Применено ${result.applied} из ${result.total}. ${failed[0].error}`
      : `Профиль активирован: ${result.applied} ограничений`);
  }

  async function restoreTelemetryProfile() {
    const ok = await confirmAction(
      "Вернуть исходные настройки?",
      "Будут восстановлены только значения, которые приложение сохранило перед изменением. Параметры, заданные вне приложения, не сбрасываются.",
      "Восстановить",
      true,
    );
    if (!ok) return;
    const result = await run("Восстановление исходных политик…", () => api("restore_telemetry_profile"));
    if (!result) return;
    state.telemetry = result.state;
    renderTelemetry(result.state);
    const failed = (result.results || []).filter((item) => !item.ok);
    toast(failed.length
      ? `Восстановлено ${result.restored} из ${result.total}. ${failed[0].error}`
      : `Исходные значения восстановлены: ${result.restored}`);
  }

  $("#btn-telemetry-apply").addEventListener("click", applyTelemetryProfile);
  $("#btn-telemetry-restore").addEventListener("click", restoreTelemetryProfile);
  $("#telemetry-list").addEventListener("click", async (event) => {
    const button = event.target.closest("[data-telemetry-id]");
    if (!button || button.disabled) return;
    const id = button.dataset.telemetryId;
    const control = state.telemetry?.controls?.find((item) => item.id === id);
    if (!control) return;
    const restoring = button.dataset.telemetryAction === "restore";
    const ok = await confirmAction(
      restoring ? "Восстановить настройку?" : "Ограничить сбор?",
      restoring
        ? `${control.name}\n\nВернётся точное значение, сохранённое перед изменением.`
        : `${control.name}\n\n${control.description}\n\nИсходное значение будет сохранено для отката.`,
      restoring ? "Восстановить" : "Ограничить",
      true,
    );
    if (!ok) return;
    const result = await run(restoring ? "Восстановление настройки…" : "Ограничение сбора…", () =>
      api(restoring ? "restore_telemetry_control" : "apply_telemetry_control", id));
    if (!result) return;
    state.telemetry = result.state;
    renderTelemetry(result.state);
    toast(result.message);
  });

  function renderChips() {
    $("#category-chips").innerHTML = state.categories.map((cat) => {
      const all = state.tweaks.filter((t) => t.category === cat.id);
      const on = all.filter((t) => t.state === "on").length;
      return `<button class="chip ${cat.id === state.category ? "is-active" : ""}" data-category="${esc(cat.id)}">${esc(cat.name)} · <span class="chip-count">${on}/${all.length}</span></button>`;
    }).join("");
  }

  $("#category-chips").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-category]");
    if (!chip) return;
    state.category = chip.dataset.category;
    renderChips();
    renderTweaks();
  });

  $("#btn-only-on").addEventListener("click", (e) => {
    state.onlyOn = !state.onlyOn;
    e.currentTarget.classList.toggle("is-active", state.onlyOn);
    e.currentTarget.setAttribute("aria-pressed", String(state.onlyOn));
    renderTweaks();
  });

  $("#tweak-search").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
    renderTweaks();
  });

  const STATE_LABEL = { on: "включено", off: "выключено", missing: "недоступно", unknown: "иное значение" };

  function renderTweaks() {
    const list = state.tweaks.filter((t) => t.category === state.category)
      .filter((t) => !state.onlyOn || t.state === "on")
      .filter((t) => {
        if (!state.search) return true;
        const hay = `${t.name} ${t.description} ${t.value_name} ${t.key_path}`.toLowerCase();
        return hay.includes(state.search);
      });

    const onCount = state.tweaks.filter((t) => t.category === state.category && t.state === "on").length;
    const available = list.filter((t) => t.state !== "missing").length;
    $("#tweak-stats").textContent =
      `Показано: ${list.length} · доступно: ${available} · включено в категории: ${onCount}`;

    if (!list.length) {
      $("#tweak-list").innerHTML = `<div class="panel"><div class="panel-body muted">Ничего не найдено. Измените запрос, категорию или снимите фильтр «только включённые».</div></div>`;
      return;
    }

    $("#tweak-list").innerHTML = list.map((t) => {
      const missing = t.state === "missing";
      const on = t.state === "on";
      const canRevert = t.state === "on" || t.state === "unknown";
      const locked = t.requires_admin && !state.admin;
      const busy = state.pending.has(t.id);
      const flash = state.flash.get(t.id);
      const open = state.details.has(t.id);
      const riskClass = t.risk === "safe" ? "badge-ok" : t.risk === "danger" ? "badge-warn" : "badge-muted";
      const stateLabel = busy
        ? (state.busyMode.get(t.id) === "revert" ? "откатываю…" : "применяю…")
        : (STATE_LABEL[t.state] || t.state);
      const stateClass = on ? "badge-on" : t.state === "unknown" ? "badge-warn" : "badge-off";
      return `
      <article class="card ${on ? "is-on" : "is-off"} ${missing ? "is-missing" : ""} ${busy ? "is-busy" : ""} ${flash ? "is-done" : ""}" data-id="${esc(t.id)}">
        <div class="card-top">
          <h3>${esc(t.name)}</h3>
          <span class="card-switch">
            <input type="checkbox" class="switch" data-toggle="${esc(t.id)}" ${on || (busy && state.busyMode.get(t.id) === "apply") ? "checked" : ""} ${missing || locked || busy ? "disabled" : ""} aria-label="Переключить твик">
          </span>
        </div>
        <p>${esc(t.description)}</p>
        <div class="card-badges">
          <span class="badge ${riskClass}">${esc(t.risk_label)}</span>
          <span class="badge ${stateClass}">${busy ? '<span class="mini-spinner"></span>' : ""}${esc(stateLabel)}</span>
          <span class="badge badge-off">${esc(t.value_name)}</span>
          ${t.restart ? '<span class="badge badge-warn">перезагрузка</span>' : ""}
        </div>
        <div class="card-foot">
          <span class="small muted">${on || t.state === "unknown"
            ? `сейчас: ${esc(t.current ?? "—")}`
            : esc(t.requires_admin ? "HKLM · нужен админ" : "HKCU")}</span>
          <div class="card-actions">
            <button class="btn btn-sm" data-apply="${esc(t.id)}" ${missing || locked || on || busy ? "disabled" : ""}>Применить</button>
            <button class="btn btn-ghost btn-sm" data-revert="${esc(t.id)}" ${missing || locked || !canRevert || busy ? "disabled" : ""}>Откатить</button>
          </div>
        </div>
        <button class="card-more" data-more="${esc(t.id)}" aria-expanded="${open ? "true" : "false"}">
          <span>${open ? "Скрыть детали" : "Подробнее"}</span>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>
        </button>
        ${open ? `
        <div class="card-details">
          <div class="detail-row"><span>Что меняется</span><b>${esc(t.description)}</b></div>
          <div class="detail-row"><span>Ключ реестра</span><code>${esc(t.key_path)}</code></div>
          <div class="detail-row"><span>Параметр</span><code>${esc(t.value_name)}</code></div>
          <div class="detail-row"><span>Тип</span><b>${esc(t.value_type)}</b></div>
          <div class="detail-row"><span>Значение «включено»</span><b>${esc(String(t.on_value))}</b></div>
          <div class="detail-row"><span>Значение «выключено»</span><b>${esc(String(t.off_value))}</b></div>
          <div class="detail-row"><span>Сейчас в системе</span><b>${esc(t.current ?? "значение отсутствует")}</b></div>
          <div class="detail-row"><span>Нужны права</span><b>${t.requires_admin ? "администратор" : "обычный пользователь"}</b></div>
          <div class="detail-row"><span>Перезагрузка</span><b>${t.restart ? "нужна" : "не нужна"}</b></div>
          <div class="detail-row"><span>Риск</span><b>${esc(t.risk_label)}</b></div>
          ${t.source ? `<div class="detail-row"><span>Откуда взято</span><b>${esc(t.source)}</b></div>` : ""}
        </div>` : ""}
        ${busy ? `<div class="card-busy"><span class="mini-spinner"></span>${state.busyMode.get(t.id) === "revert" ? "Возвращаю исходное значение…" : "Записываю в реестр и делаю бэкап…"}</div>` : ""}
      </article>`;
    }).join("");
  }

  $("#tweak-list").addEventListener("click", async (e) => {
    const moreId = e.target.closest("[data-more]")?.dataset.more;
    if (moreId) {
      if (state.details.has(moreId)) state.details.delete(moreId);
      else state.details.add(moreId);
      renderTweaks();
      return;
    }
    const applyId = e.target.closest("[data-apply]")?.dataset.apply;
    if (applyId) return changeTweak(applyId, "apply");
    const revertId = e.target.closest("[data-revert]")?.dataset.revert;
    if (revertId) return changeTweak(revertId, "revert");
  });

  $("#tweak-list").addEventListener("change", (e) => {
    const id = e.target.closest("[data-toggle]")?.dataset.toggle;
    if (!id) return;
    const wantOn = e.target.checked;
    changeTweak(id, wantOn ? "apply" : "revert");
  });

  async function changeTweak(id, mode) {
    const tweak = state.tweaks.find((t) => t.id === id);
    if (!tweak || state.pending.has(id)) return;

    const ok = await confirmAction(
      mode === "apply" ? "Применить настройку?" : "Откатить настройку?",
      `${tweak.name}\n\n${tweak.description}\n\nКлюч: ${tweak.key_path}\nПараметр: ${tweak.value_name}\n` +
        `Станет: ${mode === "apply" ? tweak.on_value : tweak.off_value}` +
        (tweak.restart ? "\n\nИзменение вступит в силу после перезагрузки." : ""),
      mode === "apply" ? "Применить" : "Откатить",
      tweak.risk === "danger",
    );
    if (!ok) { renderTweaks(); return; }

    // анимация прямо на карточке: спиннер и блокировка кнопок
    state.pending.set(id, true);
    state.busyMode.set(id, mode);
    state.flash.delete(id);
    renderTweaks();

    let res = null;
    try {
      res = await api(mode === "apply" ? "apply_tweak" : "revert_tweak", id);
    } catch (err) {
      toast(err.message || String(err), true);
    }
    state.pending.delete(id);
    state.busyMode.delete(id);

    if (!res) { renderTweaks(); return; }

    // мгновенно показываем новое состояние и подсвечиваем карточку
    tweak.state = mode === "apply" ? "on" : "off";
    tweak.current = String(mode === "apply" ? tweak.on_value : tweak.off_value);
    state.flash.set(id, mode);
    renderChips();
    renderTweaks();
    toast(res.message);

    setTimeout(() => {
      if (state.flash.get(id) === mode) {
        state.flash.delete(id);
        if (state.view === "registry") renderTweaks();
      }
    }, 1500);

    // фоновая сверка с реальным реестром
    try {
      const fresh = await api("list_tweaks");
      state.tweaks = fresh.tweaks;
      renderChips();
      if (state.view === "registry") renderTweaks();
    } catch { /* карточка уже обновлена локально */ }
  }

  $("#btn-apply-category").addEventListener("click", async () => {
    const cat = state.categories.find((c) => c.id === state.category);
    const hasDanger = state.tweaks.some((t) => t.category === state.category && t.risk === "danger");
    const ok = await confirmAction("Применить всю категорию?", `Будут включены все доступные твики категории «${cat ? cat.name : ""}». Для каждого ключа сначала создаётся .reg-бэкап.`, "Применить всё", hasDanger);
    if (!ok) return;
    const res = await run("Применение категории…", () => api("apply_category", state.category));
    if (res) {
      const failed = res.results.filter((r) => !r.ok);
      toast(`Применено ${res.applied} из ${res.total}${failed.length ? `, ошибок: ${failed.length}` : ""}`, failed.length > 0);
      const fresh = await run("Обновление…", () => api("list_tweaks"));
      if (fresh) { state.tweaks = fresh.tweaks; renderChips(); renderTweaks(); }
    }
  });

  $("#btn-revert-category").addEventListener("click", async () => {
    const cat = state.categories.find((c) => c.id === state.category);
    const hasDanger = state.tweaks.some((t) => t.category === state.category && t.risk === "danger");
    const ok = await confirmAction("Откатить всю категорию?", `Все твики категории «${cat ? cat.name : ""}» вернутся к значениям по умолчанию.`, "Откатить всё", hasDanger);
    if (!ok) return;
    const res = await run("Откат категории…", () => api("revert_category", state.category));
    if (res) {
      const failed = res.results.filter((r) => !r.ok);
      toast(`Откачено ${res.reverted} из ${res.total}${failed.length ? `, ошибок: ${failed.length}` : ""}`, failed.length > 0);
      const fresh = await run("Обновление…", () => api("list_tweaks"));
      if (fresh) { state.tweaks = fresh.tweaks; renderChips(); renderTweaks(); }
    }
  });

  /* ---------- устройства ---------- */
  async function loadDevices() {
    const data = await run("Опрос видеокарт через PowerShell…", () => api("list_devices"));
    if (!data) return;
    state.devices = data.devices;
    state.admin = data.admin;
    renderDevices();
  }

  function renderDevices() {
    if (!state.devices.length) {
      $("#device-list").innerHTML = `<div class="panel"><div class="panel-body muted">Видеокарты не найдены или PowerShell недоступен. Подробности — в логах.</div></div>`;
      return;
    }
    $("#device-list").innerHTML = state.devices.map((d) => {
      const ok = (d.status || "").toLowerCase() === "ok";
      return `
      <article class="card">
        <div class="card-top">
          <h3>${esc(d.name)}</h3>
          <span class="badge ${ok ? "badge-ok badge-dot" : "badge-warn"}">${esc(d.status || "Unknown")}</span>
        </div>
        <p class="small"><code>${esc(d.instance_id)}</code></p>
        <div class="card-foot">
          <span class="small muted">${d.problem ? `Код проблемы: ${esc(d.problem)}` : "PnP-устройство"}</span>
          <div class="card-actions">
            ${ok
              ? `<button class="btn btn-ghost btn-sm" data-device-off="${esc(d.instance_id)}" ${state.admin ? "" : "disabled"}>Отключить</button>`
              : `<button class="btn btn-sm" data-device-on="${esc(d.instance_id)}" ${state.admin ? "" : "disabled"}>Включить</button>`}
          </div>
        </div>
      </article>`;
    }).join("");
  }
  $("#btn-refresh-devices").addEventListener("click", loadDevices);
  $("#device-list").addEventListener("click", async (e) => {
    const off = e.target.closest("[data-device-off]")?.dataset.deviceOff;
    const on = e.target.closest("[data-device-on]")?.dataset.deviceOn;
    if (!off && !on) return;
    const id = off || on;
    const enabling = Boolean(on);
    const device = state.devices.find((d) => d.instance_id === id);
    const ok = await confirmAction(
      enabling ? "Включить устройство?" : "Отключить устройство?",
      `${device ? device.name : id}\n\n${enabling ? "Устройство снова станет доступным системе." : "Экран может погаснуть, если это единственная видеокарта. Драйвер не удаляется, вернуть устройство можно кнопкой «Включить»."}`,
      enabling ? "Включить" : "Отключить",
      !enabling,
    );
    if (!ok) return;
    const res = await run(enabling ? "Включение устройства…" : "Отключение устройства…", () => api("set_device", id, enabling));
    if (res) { toast(enabling ? "Устройство включено" : "Устройство отключено"); loadDevices(); }
  });

  /* ---------- скрипты ---------- */
  async function loadScripts() {
    const data = await run("Сканирование папки scripts…", () => api("list_scripts"));
    if (!data) return;
    state.scripts = data.scripts;
    state.admin = data.admin;
    renderScripts();
    renderFaceit();
  }

  const SCRIPT_STATE = {
    on: ["выполнен", "badge-on"],
    off: ["не выполнен", "badge-off"],
    missing: ["ключи не найдены", "badge-warn"],
    unknown: ["состояние неизвестно", "badge-off"],
  };

  function scriptCard(s) {
    const [stateText, stateClass] = SCRIPT_STATE[s.state] || SCRIPT_STATE.off;
    const riskClass = s.risk === "safe" ? "badge-ok" : s.risk === "danger" ? "badge-danger" : "badge-warn";
    const riskText = s.risk === "safe" ? "безопасно" : s.risk === "danger" ? "опасно" : "осторожно";
    const done = s.state === "on";
    const gpuBlocked = Boolean(s.vendor && s.vendor_compatible === false);
    const file = s.name.split("/").pop();
    return `
      <article class="card ${s.risk === "danger" ? "card-danger" : ""} ${done ? "is-on" : ""}">
        <div class="card-top"><h3>${esc(s.title)}</h3><span class="badge ${riskClass}">${riskText}</span></div>
        <p>${esc(s.description)}</p>
        <div class="card-badges">
          <span class="badge ${stateClass}">${stateText}</span>
          <span class="badge badge-off">${esc(file)}</span>
          ${gpuBlocked ? `<span class="badge badge-danger">${esc(s.vendor_reason || `Требуется ${VENDOR_RU[s.vendor] || s.vendor}`)}</span>` : ""}
          ${done && s.revert_reason ? `<span class="badge badge-warn">${esc(s.revert_reason)}</span>` : ""}
          ${s.restart ? '<span class="badge badge-warn">перезагрузка</span>' : ""}
        </div>
        <div class="card-foot">
          <span class="small muted">${(s.size / 1024).toFixed(1)} КБ · ${esc(s.kind)}</span>
          <div class="card-actions">
            ${done
              ? (s.can_revert
                ? `<button class="btn btn-ghost btn-sm" data-revert-script="${esc(s.name)}" ${!state.admin ? "disabled" : ""}>${esc(s.undo_label || "Откатить")}</button>`
                : `<button class="btn btn-ghost btn-sm" disabled>${s.revert_reason ? "Нет бэкапа" : "Применено"}</button>`)
              : `<button class="btn btn-sm" data-run="${esc(s.name)}" ${state.admin && !gpuBlocked ? "" : "disabled"}>Выполнить</button>`}
          </div>
        </div>
      </article>`;
  }

  function renderScripts() {
    const query = ($("#script-search").value || "").trim().toLowerCase();
    const list = query
      ? state.scripts.filter((s) => `${s.title} ${s.name} ${s.description}`.toLowerCase().includes(query))
      : state.scripts;
    if (!list.length) {
      $("#script-list").innerHTML = `<div class="panel"><div class="panel-body muted">${state.scripts.length ? "Ничего не найдено." : "В папке scripts нет файлов .bat, .cmd, .reg или .ps1."}</div></div>`;
      return;
    }
    const groups = new Map();
    for (const item of list) {
      const key = item.group || "scripts";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    $("#script-list").innerHTML = [...groups.entries()]
      .sort((a, b) => a[0].localeCompare(b[0], "ru"))
      .map(([group, items]) => {
        const active = items.filter((i) => i.state === "on").length;
        return `
        <div class="script-group">
          <div class="script-group-head">
            <span class="group-title">${esc(group.replace(/^материалы\/?/, "") || "scripts")}</span>
            <span class="muted small">${active ? `${active} / ${items.length} выполнено` : `${items.length} файлов`}</span>
          </div>
          <div class="cards">${items.map(scriptCard).join("")}</div>
        </div>`;
      })
      .join("");
  }

  $("#btn-open-scripts").addEventListener("click", () => run("Открытие папки…", async () => {
    await api("open_folder", "scripts"); return true;
  }));

  $("#script-search").addEventListener("input", renderScripts);

  async function revertScriptBy(name) {
    const script = state.scripts.find((s) => s.name === name);
    const ok = await confirmAction(
      "Откатить скрипт?",
      `${script ? script.title : name}\n\n${script && script.kind === "reg"
        ? "Ключи реестра вернутся к значениям, сохранённым перед запуском этого файла."
        : "Будет выполнена обратная команда: " + (script ? script.undo_label : "")}`,
      "Откатить",
      true,
    );
    if (!ok) return;
    const res = await run("Откат скрипта…", () => api("revert_script", name));
    if (res) {
      const restart = script?.restart ? ". Перезагрузите компьютер, чтобы изменения вступили в силу" : "";
      toast(`Откат выполнен; состояние обновлено${restart}`);
      await loadScripts();
    }
  }

  $("#script-list").addEventListener("click", async (e) => {
    const revertName = e.target.closest("[data-revert-script]")?.dataset.revertScript;
    if (revertName) {
      await revertScriptBy(revertName);
      return;
    }

    const name = e.target.closest("[data-run]")?.dataset.run;
    if (name) runScriptBy(name);
  });

  async function runScriptBy(name) {
    const script = state.scripts.find((s) => s.name === name);
    const warn = script && script.risk === "danger"
      ? "\n\nВНИМАНИЕ: файл помечен как опасный — он может снизить безопасность системы, сломать обновления или вызвать нестабильность, а откат не предусмотрен."
      : "";
    const ok = await confirmAction(
      "Запустить скрипт?",
      `${script ? script.title : name}\n\n${script ? script.description : ""}${warn}` +
        `\n\nФайл: ${name}\nСкрипт выполнится с правами администратора. Вывод и код возврата попадут в лог.`,
      "Выполнить",
      script?.risk === "danger",
    );
    if (!ok) return;
    const res = await run("Выполнение скрипта…", () => api("run_script", name));
    if (res) {
      $("#script-output-panel").classList.remove("hidden");
      $("#script-output").textContent = `> ${name}\nКод возврата: ${res.returncode}\n\n${res.output}`;
      const restart = script?.restart ? "; для вступления в силу нужна перезагрузка" : "";
      toast(res.returncode === 0 ? `Настройка применена${restart}` : `Скрипт завершён с кодом ${res.returncode}`, res.returncode !== 0);
      await loadScripts();
    }
  }

  $("#btn-close-output").addEventListener("click", () => $("#script-output-panel").classList.add("hidden"));

  /* ---------- инструменты ---------- */
  const VENDOR_RU = { nvidia: "NVIDIA", amd: "AMD", intel: "Intel" };
  const TOOL_GROUPS = [
    ["games", "Игры и ускорение"],
    ["system", "Система и очистка"],
  ];

  async function loadTools() {
    const data = await run("Загрузка инструментов…", () => api("list_tools"));
    if (!data) return;
    state.tools = data.tools;
    state.gpu = (data.gpu && data.gpu.vendors) || [];
    state.admin = data.admin;
    const scriptsData = await run("Чтение материалов…", () => api("list_scripts"));
    if (scriptsData) state.scripts = scriptsData.scripts;

    $("#gpu-vendor").textContent = state.gpu.length
      ? `видеокарта: ${state.gpu.map((v) => VENDOR_RU[v] || v).join(", ")}`
      : "видеокарта: не определена";
    renderToolChips();
    renderTools();
    renderFaceit();
  }

  function renderToolChips() {
    const chips = [["all", "Все"], ...TOOL_GROUPS];
    $("#tool-chips").innerHTML = chips.map(([id, name]) => {
      const count = id === "all" ? state.tools.length : state.tools.filter((t) => t.group === id).length;
      return `<button class="chip ${state.toolsGroup === id ? "is-active" : ""}" data-tool-group="${esc(id)}">${esc(name)} · ${count}</button>`;
    }).join("");
  }

  function toolAction(tool) {
    if (tool.action === "download") {
      const labels = { msi_utility: "Скачать MSI Utility", process_lasso: "Скачать Process Lasso" };
      return `<button class="btn btn-sm" data-tool-download="${esc(tool.id)}">${labels[tool.id] || "Скачать файл"}</button>`;
    }
    if (tool.action === "powershell") {
      return `<button class="btn btn-sm" data-tool-debloat="${esc(tool.id)}">Запустить Debloat</button>`;
    }
    return `<button class="btn btn-sm" data-tool-open="${esc(tool.id)}">Открыть страницу</button>`;
  }

  function renderTools() {
    const list = state.toolsGroup === "all" ? state.tools : state.tools.filter((t) => t.group === state.toolsGroup);
    $("#tool-groups").innerHTML = TOOL_GROUPS.map(([groupId, groupName]) => {
      const items = list.filter((t) => t.group === groupId);
      if (!items.length) return "";
      return `
        <div class="panel mt">
          <div class="panel-head"><h2>${groupName}</h2><span class="muted small">${items.length}</span></div>
          <div class="panel-body tools-grid">
            ${items.map(toolCard).join("")}
          </div>
        </div>`;
    }).join("") || "";
  }

  function toolCard(tool) {
    const riskClass = tool.risk === "safe" ? "badge-ok" : tool.risk === "danger" ? "badge-danger" : "badge-warn";
    const riskText = tool.risk === "safe" ? "безопасно" : tool.risk === "danger" ? "опасно" : "осторожно";
    return `
      <article class="tool-card">
        <div class="tool-head">
          <div>
            <h3>${esc(tool.title)}</h3>
            <div class="tool-tagline">${esc(tool.tagline)}</div>
          </div>
          <span class="badge ${riskClass}">${riskText}</span>
        </div>
        <p>${esc(tool.description)}</p>
        <div class="tool-actions">${toolAction(tool)}</div>
        <details class="tutorial">
          <summary>Туториал: ${tool.steps.length} шагов</summary>
          <ol>${tool.steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol>
        </details>
      </article>`;
  }

  function renderFaceit() {
    const faceit = state.scripts.filter((s) => s.name.includes("[faceit]"));
    const vendorFiles = state.scripts.filter((s) => {
      if (!s.vendor) return false;
      if (!state.gpu.length) return true;
      return state.gpu.includes(s.vendor);
    });
    const vendorNotice = state.gpu.length
      ? `Показаны настройки для вашей видеокарты: ${state.gpu.map((v) => VENDOR_RU[v] || v).join(", ")}.`
      : "Видеокарта не определена — показаны настройки и для AMD, и для NVIDIA.";

    const rows = [...faceit, ...vendorFiles].slice(0, 14);
    if (!rows.length) {
      $("#faceit-list").innerHTML = `<div class="muted small">Материалы FACEIT не найдены.</div>`;
      return;
    }
    $("#faceit-list").innerHTML = rows.map((s) => {
      const riskClass = s.risk === "safe" ? "badge-ok" : s.risk === "danger" ? "badge-danger" : "badge-warn";
      const riskText = s.risk === "safe" ? "безопасно" : s.risk === "danger" ? "опасно" : "осторожно";
      const done = s.state === "on";
      return `
        <article class="card ${done ? "is-on" : ""}">
          <div class="card-top"><h3>${esc(s.title)}</h3><span class="badge ${riskClass}">${riskText}</span></div>
          <p>${esc(s.description)}</p>
          <div class="card-badges">
            <span class="badge badge-off">${esc(s.name.split("/").pop())}</span>
            ${s.vendor ? `<span class="badge badge-off">${esc(VENDOR_RU[s.vendor] || s.vendor)}</span>` : ""}
            ${s.vendor && s.vendor_compatible === false ? `<span class="badge badge-danger">${esc(s.vendor_reason)}</span>` : ""}
            ${done ? '<span class="badge badge-on">выполнен</span>' : ""}
            ${done && s.revert_reason ? `<span class="badge badge-warn">${esc(s.revert_reason)}</span>` : ""}
            ${s.restart ? '<span class="badge badge-warn">перезагрузка</span>' : ""}
          </div>
          <div class="card-foot">
            <span class="small muted">${s.vendor && s.vendor_compatible === false ? esc(s.vendor_reason) : vendorNotice}</span>
            ${done
              ? (s.can_revert
                ? `<button class="btn btn-ghost btn-sm" data-revert-script="${esc(s.name)}" ${state.admin ? "" : "disabled"}>${esc(s.undo_label || "Откатить")}</button>`
                : `<button class="btn btn-ghost btn-sm" disabled>${s.revert_reason ? "Нет бэкапа" : "Применено"}</button>`)
              : `<button class="btn btn-sm" data-run="${esc(s.name)}" ${state.admin && s.vendor_compatible !== false ? "" : "disabled"}>Выполнить</button>`}
          </div>
        </article>`;
    }).join("");
  }

  $("#tool-chips").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-tool-group]");
    if (!chip) return;
    state.toolsGroup = chip.dataset.toolGroup;
    renderToolChips();
    renderTools();
  });

  $("#faceit-list").addEventListener("click", (e) => {
    const revertName = e.target.closest("[data-revert-script]")?.dataset.revertScript;
    if (revertName) { revertScriptBy(revertName); return; }
    const name = e.target.closest("[data-run]")?.dataset.run;
    if (name) runScriptBy(name);
  });

  $("#tool-groups").addEventListener("click", async (e) => {
    const downloadId = e.target.closest("[data-tool-download]")?.dataset.toolDownload;
    const openId = e.target.closest("[data-tool-open]")?.dataset.toolOpen;
    const debloat = e.target.closest("[data-tool-debloat]");
    if (downloadId) {
      const tool = state.tools.find((t) => t.id === downloadId);
      const ok = await confirmAction(
        "Скачать файл?",
        `${tool ? tool.title : downloadId}\n\nФайл будет сохранён в папку загрузок приложения и откроется Проводник.`,
        "Скачать",
      );
      if (!ok) return;
      const res = await run("Скачивание…", () => api("download_tool", downloadId));
      if (res) toast(res.path ? `Готово: ${res.path}` : res.message || "Скачано");
      return;
    }
    if (openId) {
      await run("Открытие страницы…", () => api("open_tool_link", openId));
      return;
    }
    if (debloat) {
      const ok = await confirmAction(
        "Запустить Debloat?",
        "Откроется окно PowerShell, скрипт скачается с debloat.raphi.re и предложит меню.\n\n" +
          "Выберите базовую настройку вручную. Перед этим желательно создать точку восстановления.",
        "Запустить",
        true,
      );
      if (!ok) return;
      const res = await run("Запуск Debloat…", () => api("run_debloat"));
      if (res) toast(res.message);
    }
  });

  $("#btn-open-downloads").addEventListener("click", async () => {
    const res = await run("Открываем папку…", () => api("open_folder", "downloads"));
    if (res) toast(`Загрузки: ${res.path}`);
  });
  /* ---------- бэкапы ---------- */
  async function loadBackups() {
    const data = await run("Чтение списка бэкапов…", () => api("list_backups"));
    if (!data) return;
    state.backups = data.backups;
    $("#backup-dir").textContent = `Папка: ${data.dir}`;
    if (!state.backups.length) {
      $("#backup-list").innerHTML = `<div class="panel"><div class="panel-body muted">Бэкапов нет. Создайте первый перед изменениями.</div></div>`;
      loadRestorePoints();
      return;
    }
    $("#backup-list").innerHTML = state.backups.map((b) => `
      <div class="list-row">
        <div class="list-main">
          <div class="list-title">${esc(b.name)}</div>
          <div class="list-sub">${fmtDate(b.created)} · ${esc(b.note || "без описания")} · .reg: ${esc(b.reg_files)}${b.type === "action" ? " · точечный" : ""}</div>
        </div>
        <div class="list-actions">
          <button class="btn btn-sm" data-restore="${esc(b.name)}" ${b.reg_files > 0 ? "" : "disabled"}>Восстановить</button>
          <button class="btn btn-ghost btn-sm" data-delete="${esc(b.name)}">Удалить</button>
        </div>
      </div>`).join("");
  }

  $("#btn-open-backups").addEventListener("click", () => run("Открытие папки…", async () => {
    await api("open_folder", "backups"); return true;
  }));

  $("#btn-create-backup").addEventListener("click", async () => {
    const res = await run("Создание бэкапа…", () => api("create_backup"));
    if (res) { toast(`Бэкап «${res.name}» создан: ${res.exported} ключей`); loadBackups(); }
  });

  const PROFILE_GPU_NAMES = { amd: "AMD", nvidia: "NVIDIA", intel: "Intel" };

  function setProfileStep(active) {
    document.querySelectorAll("#profile-import-steps [data-profile-step]").forEach((step) => {
      const number = Number(step.dataset.profileStep);
      step.classList.toggle("is-complete", number < active);
      step.classList.toggle("is-active", number === active);
    });
  }

  function renderProfilePreview(preview) {
    state.profilePreview = preview;
    setProfileStep(2);
    const detectedVendors = preview.local_vendors || [];
    $("#profile-preview-file").textContent = `${preview.filename} · создан ${fmtDate(preview.created)} · видеокарта в профиле: ${(preview.source_vendors || []).map((v) => PROFILE_GPU_NAMES[v] || v).join(", ") || "не определена"} · на этом ПК: ${(preview.local_vendors || []).map((v) => PROFILE_GPU_NAMES[v] || v).join(", ") || "не определена"}`;
    const groups = [
      ["В профиле включено", (preview.applicable || []).filter((item) => item.state === "on")],
      ["В профиле выключено", (preview.applicable || []).filter((item) => item.state === "off")],
      ["Пропущены: другое семейство видеокарты", preview.incompatible || [], "muted"],
      ["Пропущены: параметр недоступен на этом ПК", preview.unavailable || [], "muted"],
      ["Неизвестные настройки из новой/другой версии", preview.unknown || [], "muted"],
    ].filter(([, items]) => items.length);
    if (!groups.length) {
      groups.push(["Совместимых настроек нет", ["Профиль не будет применён на этом компьютере."]]);
    }
    $("#profile-preview-details").innerHTML = groups.map(([title, items, muted]) => `
      <div class="profile-preview-group"><strong>${esc(title)} · ${items.length}</strong><ul>${items.map((item) => {
        if (typeof item === "string") return `<li class="profile-state-row is-muted"><span class="profile-state-dot" aria-hidden="true"></span><span>${esc(item)}</span></li>`;
        const current = item.current_state;
        const currentLabel = current === "on" ? "сейчас включено" : current === "off" ? "сейчас выключено" : "состояние не определено";
        const targetLabel = item.state === "on" ? "будет включено" : "будет выключено";
        return `<li class="profile-state-row ${current === "on" ? "is-on" : current === "off" ? "is-off" : "is-muted"}" title="${esc(currentLabel)}"><span class="profile-state-dot" aria-hidden="true"></span><span class="profile-state-copy"><span>${esc(item.name)}${item.restart ? " · нужна перезагрузка" : ""}</span><small>${esc(currentLabel)} · ${targetLabel}</small></span></li>`;
      }).join("")}</ul></div>`).join("");
    const noGpuNote = detectedVendors.length
      ? "Точка показывает состояние на этом ПК сейчас: зелёная — включено, красная — выключено. Под названием указано, какое состояние задаст профиль."
      : "Видеокарта не обнаружена. Настройки AMD и NVIDIA из профиля будут пропущены и не изменят систему. Точки показывают текущие состояния остальных настроек; под названием указано, что задаст профиль.";
    $("#profile-preview-intro").textContent = noGpuNote;
    $("#btn-apply-profile").disabled = !(preview.applicable || []).length;
    $("#profile-import-preview").classList.remove("hidden");
    $("#profile-import-preview").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  $("#btn-export-profile").addEventListener("click", async () => {
    const result = await run("Создаю переносимый профиль…", () => api("export_portable_profile"));
    if (!result || result.cancelled) return;
    toast(`Профиль ${result.filename} сохранён · настроек: ${result.count}${result.skipped_gpu ? ` · несовместимых GPU твиков пропущено: ${result.skipped_gpu}` : ""}`);
  });

  $("#btn-import-profile").addEventListener("click", async () => {
    state.profilePreview = null;
    $("#profile-import-preview").classList.add("hidden");
    setProfileStep(1);
    const preview = await run("Проверяю файл профиля и совместимость…", () => api("select_portable_profile"));
    if (!preview || preview.cancelled) return;
    renderProfilePreview(preview);
  });

  $("#btn-reset-profile-restore-choice").addEventListener("click", async () => {
    const saved = await run("Сбрасываю выбор точки восстановления…", () => api("save_settings", { profile_restore_point: null }));
    if (saved) {
      state.settings = saved;
      $("#btn-reset-profile-restore-choice").disabled = true;
      toast("Перед следующим импортом снова появится выбор точки восстановления.");
    }
  });

  $("#btn-cancel-profile").addEventListener("click", () => {
    state.profilePreview = null;
    $("#profile-import-preview").classList.add("hidden");
    setProfileStep(1);
  });

  $("#btn-apply-profile").addEventListener("click", async () => {
    const preview = state.profilePreview;
    if (!preview || !(preview.applicable || []).length) return;
    const willEnable = preview.applicable.filter((item) => item.state === "on").length;
    const willDisable = preview.applicable.filter((item) => item.state === "off").length;
    const text = `Профиль задаст состояние ${preview.applicable.length} настроек: включит ${willEnable} и выключит ${willDisable}. Список показан в карточке профиля.`
      + ((preview.incompatible || []).length ? ` Настройки для другого семейства видеокарты будут пропущены: ${(preview.incompatible || []).length}.` : "")
      + "\n\nПеред изменениями приложение создаст локальный полный бэкап. Параметры вне каталога приложения не трогаются.";
    let restoreChoice = state.settings.profile_restore_point;
    if (restoreChoice === null || restoreChoice === undefined) {
      $("#modal-title").textContent = "Защитить Windows перед импортом?";
      $("#modal-text").textContent = `${text}\n\nТочка восстановления Windows позволит вернуть системное состояние. Она не заменяет полный бэкап настроек приложения. Можно создать точку сейчас или пропустить этот шаг.`;
      $("#profile-restore-remember-check").checked = false;
      $("#profile-restore-remember").classList.remove("hidden");
      $("#modal-skip").classList.remove("hidden");
      $("#modal-cancel").textContent = "Отменить импорт";
      $("#modal-ok").textContent = "Создать точку";
      $("#modal").classList.remove("hidden");
      $("#modal-ok").focus();
      const choice = await new Promise((resolve) => { modalResolve = resolve; });
      if (choice === false) return;
      restoreChoice = choice !== "skip";
      if ($("#profile-restore-remember-check").checked) {
        const saved = await run("Сохраняю выбор…", () => api("save_settings", { profile_restore_point: restoreChoice }));
        if (saved) state.settings = saved;
      }
    }
    if (restoreChoice) {
      const point = await run("Создаю точку восстановления Windows…", () => api("create_restore_point"));
      if (!point) return;
      toast(`Точка восстановления создана · ${point.time || point.description}`);
    }
    const ok = await confirmAction("Применить переносимый профиль?", `${text}\n\nСейчас будет создан локальный бэкап Cosmic Optimizer перед изменениями.`, "Создать бэкап и применить", true);
    if (!ok) return;
    setProfileStep(3);
    const job = await run("Запускаю импорт профиля…", () => api("apply_portable_profile"));
    if (!job) {
      state.profilePreview = null;
      $("#profile-import-preview").classList.add("hidden");
      return;
    }
    const status = await waitJob(job.job, () => {}, 900);
    if (status.status === "error") {
      toast(status.error || "Не удалось применить профиль", true);
      setProfileStep(2);
      return;
    }
    const result = status.result || {};
    state.profilePreview = null;
    $("#profile-import-preview").classList.add("hidden");
    const failures = result.failed || [];
    const enabledCount = result.applied.filter((item) => item.state === "on").length;
    const disabledCount = result.applied.filter((item) => item.state === "off").length;
    toast(`Включено ${enabledCount}, выключено ${disabledCount}, без изменений ${result.unchanged.length}, ошибок ${failures.length}. Бэкап: ${result.backup}`, failures.length > 0);
    if (failures.length) toast(failures.slice(0, 3).map((item) => `${item.name}: ${item.error}`).join("\n"), true);
    if (result.needs_restart) toast("Часть настроек вступит в силу после перезагрузки.");
    if (result.needs_restart) {
      const reboot = await confirmAction(
        "Настройки применены — перезагрузить компьютер сейчас?",
        "Часть параметров начнёт действовать только после перезагрузки. Если сейчас открыты важные файлы или приложения, выберите «Позже» и перезагрузите ПК самостоятельно.",
        "Перезагрузить сейчас",
        true,
      );
      if (reboot) {
        const scheduled = await run("Перезагружаю компьютер…", () => api("reboot_now"));
        if (scheduled) toast("Перезагрузка запущена.");
      } else {
        toast("Перезагрузку можно выполнить позже.");
      }
    }
    if (state.view === "backups") loadBackups();
    if (state.view === "registry") loadRegistry();
  });

  async function createRestorePoint() {
    const ok = await confirmAction(
      "Создать точку восстановления?",
      "Windows сохранит снимок системных файлов и реестра, к которому можно вернуться через «Восстановление системы».\n\n"
      + "Занимает от 10 секунд до минуты и немного места на диске. Если «Защита системы» выключена, "
      + "приложение включит её для системного диска.",
      "Создать",
      true,
    );
    if (!ok) return;
    const res = await run("Создание точки восстановления… это может занять до минуты", () => api("create_restore_point"));
    if (res) {
      toast(res.message);
      if (state.view === "backups") loadRestorePoints();
    }
  }

  async function loadRestorePoints() {
    const data = await run("Чтение точек восстановления…", () => api("list_restore_points"));
    if (!data) return;
    const box = $("#restore-point-list");
    if (!data.points.length) {
      box.innerHTML = `<div class="muted small">Точек восстановления нет или «Защита системы» выключена. Кнопка «Точка восстановления» создаст первую.</div>`;
      return;
    }
    box.innerHTML = data.points.map((p) => `
      <div class="list-row">
        <div class="list-main">
          <div class="list-title">${esc(p.description || "Без описания")}</div>
          <div class="list-sub">${esc(p.time || "—")} · №${esc(p.sequence)}</div>
        </div>
        <div class="list-actions"><span class="badge badge-off">Windows</span></div>
      </div>`).join("");
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-restore-point]")) createRestorePoint();
  });
  $("#btn-refresh-points").addEventListener("click", loadRestorePoints);

  $("#backup-list").addEventListener("click", async (e) => {
    const restore = e.target.closest("[data-restore]")?.dataset.restore;
    if (restore) {
      const ok = await confirmAction("Восстановить бэкап?", `Все .reg-файлы из «${restore}» будут импортированы в реестр. Текущие значения перезапишутся.`, "Восстановить", true);
      if (!ok) return;
      const res = await run("Восстановление реестра…", () => api("restore_backup", restore));
      if (res) {
        toast(`Восстановлено файлов: ${res.restored}${res.failed.length ? `, ошибок: ${res.failed.length}` : ""}`, res.failed.length > 0);
        loadBackups();
      }
      return;
    }
    const del = e.target.closest("[data-delete]")?.dataset.delete;
    if (del) {
      const ok = await confirmAction("Удалить бэкап?", `Папка «${del}» будет удалена безвозвратно.`, "Удалить");
      if (!ok) return;
      const res = await run("Удаление…", () => api("delete_backup", del));
      if (res) { toast("Бэкап удалён"); loadBackups(); }
    }
  });

  /* ---------- логи ---------- */
  // "2026-11-15 23:23:56 | INFO    | сообщение" → три колонки
  const LOG_RE = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*([A-Z]+)\s*\|\s?([\s\S]*)$/;

  const LEVEL_RU = { INFO: "инфо", WARNING: "внимание", ERROR: "ошибка", CRITICAL: "критично", DEBUG: "отладка" };

  function renderLogLines(lines, target) {
    if (!lines.length) {
      target.innerHTML = `<span class="log-empty">Журнал пуст.</span>`;
      return;
    }
    target.innerHTML = lines.map((line) => {
      const m = line.match(LOG_RE);
      if (!m) return `<span class="log-line"><span class="log-ts"></span><span class="log-lvl"></span><span class="log-msg">${esc(line)}</span></span>`;
      const level = m[2].toLowerCase();
      return `<span class="log-line log-${esc(level)}">`
        + `<span class="log-ts">${esc(m[1])}</span>`
        + `<span class="log-lvl">${esc(LEVEL_RU[m[2]] || m[2].toLowerCase())}</span>`
        + `<span class="log-msg">${esc(m[3])}</span>`
        + `</span>`;
    }).join("");
  }

  async function loadLogs() {
    const data = await run("Чтение лога…", () => api("get_logs", 500));
    if (!data) return;
    $("#log-path").textContent = data.path;
    const view = $("#log-view");
    renderLogLines(data.lines, view);
    view.scrollTop = view.scrollHeight;
  }

  async function copyText(text, label) {
    try {
      await navigator.clipboard.writeText(text);
      toast(`${label} скопирован в буфер обмена`);
      return;
    } catch { /* WebView может запретить прямой доступ — ниже запасной путь */ }
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    area.remove();
    toast(ok ? `${label} скопирован в буфер обмена` : "Не удалось скопировать", !ok);
  }

  $("#btn-refresh-logs").addEventListener("click", loadLogs);
  $("#btn-copy-logs").addEventListener("click", async () => {
    const data = await run("Подготовка лога…", () => api("get_log_text"));
    if (!data) return;
    await copyText(data.text || "Журнал пуст.", "Лог");
  });
  $("#btn-export-logs").addEventListener("click", async () => {
    const res = await run("Экспорт лога…", () => api("export_logs"));
    if (res) toast(`Лог сохранён: ${res.path}`);
  });
  $("#btn-clear-logs").addEventListener("click", async () => {
    const ok = await confirmAction("Очистить лог?", "Текущий файл app.log будет обнулён. Старые записи не восстановить.", "Очистить");
    if (!ok) return;
    const res = await run("Очистка…", () => api("clear_logs"));
    if (res) { toast(res.message); loadLogs(); }
  });

  /* ---------- настройки ---------- */
  async function loadSettings() {
    const settings = await run("Чтение настроек…", () => api("get_settings"));
    if (!settings) return;
    state.settings = settings;
    $("#set-confirmations").checked = Boolean(settings.confirmations);
    $("#set-autobackup").checked = Boolean(settings.auto_backup);
    $("#set-backup-dir").value = settings.backups_dir || "";
    $("#about-version").textContent = state.system
      ? `Cosmic Optimizer v${state.system.app_version} · ${state.system.app_author} · pywebview · Python`
      : "Cosmic Optimizer";
    $("#about-data").textContent = state.paths.data || "";
  }

  async function saveSettings(patch) {
    const res = await run("Сохранение настроек…", () => api("save_settings", patch));
    if (res) {
      state.settings = res;
      toast("Настройки сохранены");
      return true;
    }
    return false;
  }

  $("#set-confirmations").addEventListener("change", async (e) => {
    await saveSettings({ confirmations: e.target.checked });
  });
  $("#set-autobackup").addEventListener("change", async (e) => {
    const ok = await saveSettings({ auto_backup: e.target.checked });
    if (!ok) e.target.checked = !e.target.checked;
  });
  $("#btn-save-dir").addEventListener("click", async () => {
    const dir = $("#set-backup-dir").value.trim();
    if (!dir) { toast("Укажите путь к папке бэкапов", true); return; }
    await saveSettings({ backups_dir: dir });
    const fresh = await run("Проверка…", () => api("get_settings"));
    if (fresh) $("#set-backup-dir").value = fresh.backups_dir;
  });
  $("#btn-reset-settings").addEventListener("click", async () => {
    const ok = await confirmAction("Сбросить настройки?", "Подтверждения и автобэкап вернутся к значениям по умолчанию. Твики и бэкапы не затрагиваются.", "Сбросить");
    if (!ok) return;
    const res = await run("Сброс…", () => api("reset_settings"));
    if (res) { toast("Настройки сброшены"); loadSettings(); }
  });
  $("#btn-open-data").addEventListener("click", () => run("Открытие папки…", async () => {
    await api("open_folder", "data"); return true;
  }));
  $("#btn-quit").addEventListener("click", async () => {
    const ok = await confirmAction("Закрыть приложение?", "Все изменения уже применены в реестре. Незавершённых операций нет.", "Закрыть");
    if (!ok) return;
    await run("Выход…", () => api("quit_app"));
  });
  $("#btn-uninstall").addEventListener("click", async () => {
    const ok = await confirmAction(
      "Вы действительно хотите полностью удалить Cosmic Optimizer?",
      "Будут удалены файл CosmicOptimizer.exe и локальные данные приложения: настройки, логи, бэкапы и снимки для отката. Это действие нельзя отменить. Уже применённые настройки Windows останутся; восстановите их перед удалением, если хотите вернуть исходное состояние.",
      "Удалить полностью",
      true,
    );
    if (!ok) return;
    const result = await run("Планирование удаления…", () => api("uninstall_app"));
    if (result) toast("Приложение и его локальные данные будут удалены после закрытия.");
  });

  /* ---------- старт ---------- */
  /* ---------- skeleton ---------- */
  const el = (sel) => document.querySelector(sel);
  const skelLine = (width) => `<div class="skel-line" style="width:${width}%"></div>`;

  function skeletonCards(count, tall) {
    return `<div class="cards">${Array.from({ length: count }, () => `
      <div class="card skel-card${tall ? " skel-tall" : ""}">
        ${skelLine(58)}
        ${skelLine(92)}
        ${skelLine(76)}
        <div class="skel-line skel-short" style="width:34%"></div>
      </div>`).join("")}</div>`;
  }

  function skeletonRows(count) {
    return `<div class="list">${Array.from({ length: count }, () => `
      <div class="list-row skel-row">${skelLine(40)}${skelLine(72)}</div>`).join("")}</div>`;
  }

  function skeletonStats(count) {
    return Array.from({ length: count }, () => `
      <div class="stat skel-card">${skelLine(38)}${skelLine(64)}${skelLine(52)}</div>`).join("");
  }

  const SKELETONS = {
    dashboard: () => { if (el("#sys-cards")) el("#sys-cards").innerHTML = skeletonStats(4); },
    registry: () => { if (el("#tweak-list")) el("#tweak-list").innerHTML = skeletonCards(6, true); },
    devices: () => { if (el("#device-list")) el("#device-list").innerHTML = skeletonCards(2, true); },
    scripts: () => { if (el("#script-list")) el("#script-list").innerHTML = skeletonCards(6, true); },
    tools: () => { if (el("#tool-groups")) el("#tool-groups").innerHTML = skeletonCards(4, true); },
    backups: () => { if (el("#backup-list")) el("#backup-list").innerHTML = skeletonRows(4); },
    maintenance: () => {
      if (el("#junk-list")) el("#junk-list").innerHTML = skeletonRows(6);
      if (el("#disk-list")) el("#disk-list").innerHTML = skeletonRows(2);
      if (el("#measure-list")) el("#measure-list").innerHTML = skeletonRows(2);
    },
  };

  function showSkeleton(view) {
    try {
      if (SKELETONS[view]) SKELETONS[view]();
    } catch (err) {
      /* скелетон — только оформление, ошибки игнорируем */
    }
  }

  /* ---------- мониторинг ---------- */
  const history = { cpu: [], ram: [], gpu: [] };
  const HISTORY_LIMIT = 120; // 3 минуты при опросе раз в 1.5 сек
  const POLL_MS = 1000;
  // 15 кадров/с выглядят плавно для графика; тяжёлые эффекты свечения уже убраны.
  const FRAME_INTERVAL = 1000 / 15;
  let monitorTimer = null;
  let monitorPaused = false;
  let monitorBusy = false;
  let monitorRaf = 0;
  let lastFrameAt = 0;
  let lastSampleAt = 0;
  // сколько интервалов помещается по ширине: пока точек мало — они растянуты на весь график
  let chartSpan = 1;

  // Показываемые значения плавно догоняют измеренные — без рывков раз в секунду.
  const gauges = {
    cpu: { value: 0, target: 0, known: false, format: (v) => `${Math.round(v)}%`, percent: (v) => v },
    ram: { value: 0, target: 0, known: false, format: (v) => `${Math.round(v)}%`, percent: (v) => v },
    gpu: { value: 0, target: 0, known: false, format: (v) => `${Math.round(v)}%`, percent: (v) => v },
    temp: {
      value: 0,
      target: 0,
      known: false,
      format: (v) => `${Math.round(v)}°C`,
      percent: (v) => Math.max(0, Math.min(100, v)),
    },
  };

  function setGauge(key, value, options = {}) {
    const gauge = gauges[key];
    const note = el(`#m-${key}-note`);
    if (note && options.note) note.textContent = options.note;
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      gauge.known = false;
      return;
    }
    gauge.known = true;
    gauge.target = Number(value);
    if (options.percent) gauge.percent = options.percent;
  }

  function paintGauges(dt) {
    const k = 1 - Math.exp(-dt / 280); // скорость догоняния не зависит от FPS
    for (const [key, gauge] of Object.entries(gauges)) {
      const valueNode = el(`#m-${key}`);
      const barNode = el(`#m-${key}-bar`);
      if (!valueNode || !barNode) continue;
      if (!gauge.known) {
        valueNode.textContent = "н/д";
        barNode.style.transform = "scaleX(0)";
      barNode.classList.remove("is-high", "is-good");
        continue;
      }
      gauge.value += (gauge.target - gauge.value) * k;
      if (Math.abs(gauge.target - gauge.value) < 0.05) gauge.value = gauge.target;
      valueNode.textContent = gauge.format(gauge.value);
      const percent = Math.max(0, Math.min(100, gauge.percent(gauge.value)));
      barNode.style.transform = `scaleX(${percent / 100})`;
      barNode.classList.toggle("is-high", percent >= (key === "temp" ? 80 : 85));
      barNode.classList.toggle("is-good", percent <= (key === "temp" ? 60 : 60));
    }

    // масштаб графика меняется плавно, а не рывком на каждой новой точке
    const targetSpan = Math.max(1, Math.min(HISTORY_LIMIT - 1, history.cpu.length - 1));
    chartSpan += (targetSpan - chartSpan) * k;
    if (Math.abs(targetSpan - chartSpan) < 0.01) chartSpan = targetSpan;
  }

  function fmtUptime(seconds) {
    if (!seconds && seconds !== 0) return "—";
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (days) return `${days} д ${hours} ч`;
    if (hours) return `${hours} ч ${minutes} м`;
    return `${minutes} м`;
  }

  function fmtGb(megabytes) {
    if (megabytes === null || megabytes === undefined) return "—";
    return `${(megabytes / 1024).toFixed(1)} ГБ`;
  }

  function renderMetrics(data) {
    setGauge("cpu", data.cpu, {
      note: data.cores ? `${data.cores} потоков` : "загрузка процессора",
    });
    setGauge("ram", data.ram_percent, {
      note: `${fmtGb(data.ram_used_mb)} из ${fmtGb(data.ram_total_mb)}`,
    });
    setGauge("gpu", data.gpu, {
      note: data.gpu_supported ? "Windows GPU Engine · самый занятый движок" : "счётчики GPU недоступны",
    });
    setGauge("temp", data.temp, {
      format: (v) => `${Math.round(v)}°C`,
      note: data.temp === null || data.temp === undefined ? "датчик GPU недоступен в драйвере" : "датчик драйвера видеокарты",
    });

    if (el("#m-proc")) el("#m-proc").textContent = data.processes ?? "—";
    if (el("#m-mem")) el("#m-mem").textContent = `${fmtGb(data.ram_used_mb)} / ${fmtGb(data.ram_total_mb)}`;
    if (el("#m-uptime")) el("#m-uptime").textContent = fmtUptime(data.uptime);
    if (el("#m-gpu-name")) el("#m-gpu-name").textContent = data.gpu_name || "—";

    if (data.cpu !== null && data.cpu !== undefined) pushHistory("cpu", data.cpu);
    if (data.ram_percent !== null && data.ram_percent !== undefined) pushHistory("ram", data.ram_percent);
    if (data.gpu !== null && data.gpu !== undefined) pushHistory("gpu", data.gpu);
  }

  function pushHistory(key, value) {
    history[key].push(Number(value));
    if (history[key].length > HISTORY_LIMIT) history[key].shift();
  }

  function drawChart() {
    const canvas = el("#metrics-chart");
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
    const width = Math.round(rect.width * dpr);
    const height = Math.round(rect.height * dpr);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const pad = { top: 12, right: 10, bottom: 8, left: 30 };
    const plotW = rect.width - pad.left - pad.right;
    const plotH = rect.height - pad.top - pad.bottom;
    const baseY = pad.top + plotH;

    ctx.font = "9px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const value of [100, 50, 0]) {
      const y = pad.top + plotH - (value / 100) * plotH;
      ctx.strokeStyle = value === 0 ? "rgba(255,255,255,0.13)" : "rgba(255,255,255,0.045)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y + 0.5);
      ctx.lineTo(rect.width - pad.right, y + 0.5);
      ctx.stroke();
      if (value > 0) {
        ctx.fillStyle = "rgba(255,255,255,0.26)";
        ctx.fillText(`${value}`, pad.left - 7, y);
      }
    }

    const stepX = plotW / Math.max(1, chartSpan);
    const right = pad.left + plotW;
    const full = history.cpu.length >= HISTORY_LIMIT;
    // линия течёт влево всё время между замерами, а не сдвигается рывком
    const phase = monitorPaused || !lastSampleAt || !full
      ? 0
      : Math.min(1, (performance.now() - lastSampleAt) / POLL_MS);

    const pointsOf = (values, live) =>
      values.map((value, index) => {
        const shown = index === values.length - 1 && typeof live === "number" ? live : value;
        return [
          right - (values.length - 1 - index + phase) * stepX,
          pad.top + plotH - (Math.max(0, Math.min(100, shown)) / 100) * plotH,
        ];
      });

    const tracePath = (points) => {
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 0; i < points.length - 1; i += 1) {
        const p0 = points[i - 1] || points[i];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[i + 2] || p2;
        ctx.bezierCurveTo(
          p1[0] + (p2[0] - p0[0]) / 6,
          p1[1] + (p2[1] - p0[1]) / 6,
          p2[0] - (p3[0] - p1[0]) / 6,
          p2[1] - (p3[1] - p1[1]) / 6,
          p2[0],
          p2[1],
        );
      }
    };

    if (history.cpu.length < 2) {
      ctx.fillStyle = "rgba(255,255,255,0.3)";
      ctx.textAlign = "center";
      ctx.font = "11px system-ui, -apple-system, sans-serif";
      ctx.fillText("Собираю данные…", rect.width / 2, rect.height / 2);
      return;
    }

    const ramPoints = pointsOf(history.ram, gauges.ram.known ? gauges.ram.value : undefined);
    // линии не должны заезжать на подписи оси слева
    ctx.save();
    ctx.beginPath();
    ctx.rect(pad.left, 0, plotW, rect.height);
    ctx.clip();
    tracePath(ramPoints);
    ctx.strokeStyle = "rgba(255,255,255,0.34)";
    ctx.lineWidth = 1.3;
    ctx.lineJoin = "round";
    ctx.setLineDash([5, 5]);
    ctx.stroke();
    ctx.setLineDash([]);

    const cpuPoints = pointsOf(history.cpu, gauges.cpu.known ? gauges.cpu.value : undefined);
    tracePath(cpuPoints);
    ctx.strokeStyle = "rgba(255,255,255,0.95)";
    ctx.lineWidth = 1.8;
    ctx.lineJoin = "round";
    ctx.stroke();

    // заливка под CPU
    const lastCpu = cpuPoints[cpuPoints.length - 1];
    const firstCpu = cpuPoints[0];
    ctx.lineTo(lastCpu[0], baseY);
    ctx.lineTo(firstCpu[0], baseY);
    ctx.closePath();
    const fillGradient = ctx.createLinearGradient(0, pad.top, 0, baseY);
    fillGradient.addColorStop(0, "rgba(255,255,255,0.20)");
    fillGradient.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = fillGradient;
    ctx.fill();

    // точка на конце линии CPU
    ctx.beginPath();
    ctx.arc(lastCpu[0], lastCpu[1], 2.6, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.restore();
  }

  function monitorFrame(now) {
    if (document.hidden) {
      monitorRaf = 0;
      return;
    }
    const dt = lastFrameAt ? Math.min(120, now - lastFrameAt) : 16;
    lastFrameAt = now;
    paintGauges(dt);
    drawChart();
    if (monitorTimer) monitorRaf = window.setTimeout(() => {
      monitorRaf = requestAnimationFrame(monitorFrame);
    }, FRAME_INTERVAL);
  }

  async function monitorTick() {
    if (document.hidden || monitorPaused || monitorBusy) return;
    monitorBusy = true;
    try {
      const data = await api("get_metrics");
      renderMetrics(data);
      lastSampleAt = performance.now();
      const live = el("#monitor-live");
      if (live) live.classList.add("is-live");
    } catch (err) {
      const sub = el("#monitor-sub");
      if (sub) sub.textContent = err.message;
    } finally {
      monitorBusy = false;
    }
  }

  function startMonitor() {
    if (monitorTimer || monitorPaused) return;
    lastFrameAt = 0;
    monitorTick();
    monitorTimer = setInterval(monitorTick, POLL_MS);
    if (!document.hidden) monitorRaf = requestAnimationFrame(monitorFrame);
  }

  function stopMonitor() {
    if (monitorTimer) clearInterval(monitorTimer);
    monitorTimer = null;
    if (monitorRaf) {
      clearTimeout(monitorRaf);
      cancelAnimationFrame(monitorRaf);
    }
    monitorRaf = 0;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (monitorRaf) {
        clearTimeout(monitorRaf);
        cancelAnimationFrame(monitorRaf);
      }
      monitorRaf = 0;
      return;
    }
    if (monitorTimer && !monitorPaused && !monitorRaf) {
      lastFrameAt = 0;
      monitorRaf = requestAnimationFrame(monitorFrame);
    }
  });

  if (el("#btn-monitor-toggle")) {
    el("#btn-monitor-toggle").addEventListener("click", () => {
      monitorPaused = !monitorPaused;
      el("#btn-monitor-toggle").textContent = monitorPaused ? "Продолжить" : "Пауза";
      const live = el("#monitor-live");
      if (live) live.classList.toggle("is-live", !monitorPaused);
      if (el("#monitor-sub")) {
        el("#monitor-sub").textContent = monitorPaused
          ? "Обновление приостановлено"
          : "Плавное обновление в реальном времени";
      }
      if (monitorPaused) stopMonitor();
      else startMonitor();
    });
  }

  window.addEventListener("resize", drawChart);

  /* ---------- обслуживание ---------- */
  const JUNK_DEFAULT = new Set(["temp", "thumbnails", "browsers"]);
  let junkSizes = {};
  let junkChecked = new Set(JUNK_DEFAULT);

  function fmtBytes(bytes) {
    if (bytes === null || bytes === undefined) return "—";
    if (bytes < 1024) return `${bytes} Б`;
    const units = ["КБ", "МБ", "ГБ"];
    let value = bytes / 1024;
    let index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value /= 1024;
      index += 1;
    }
    return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[index]}`;
  }

  function riskBadge(risk) {
    if (risk === "safe") return '<span class="badge badge-ok">безопасно</span>';
    if (risk === "danger") return '<span class="badge badge-danger">опасно</span>';
    return '<span class="badge badge-warn">осторожно</span>';
  }

  async function loadBenchmark() {
    const data = await run("Определяю доступные диски…", () => api("disk_info"));
    if (!data) return;
    const select = $("#benchmark-drive");
    const volumeByLetter = new Map((data.volumes || []).map((volume) => [volume.letter, volume]));
    select.innerHTML = (data.volumes || []).map((volume) => `<option value="${esc(volume.letter)}">${esc(volume.letter)}: ${esc(volume.label || "Локальный диск")} · ${esc(volume.fs || "ФС н/д")} · свободно ${fmtBytes(volume.free)} из ${fmtBytes(volume.size)}</option>`).join("");
    select.onchange = () => {
      const volume = volumeByLetter.get(select.value);
      $("#benchmark-drive-info").textContent = volume ? `${volume.letter}: ${volume.label || "Локальный диск"} · ${volume.fs || "файловая система не определена"} · занято ${volume.used_percent}% · здоровье тома: ${volume.health || "нет данных"}` : "Сведения о томе недоступны.";
    };
    select.onchange();
    $("#btn-start-benchmark").disabled = !(data.volumes || []).length;
    if (!data.volumes?.length) select.innerHTML = '<option value="">Нет доступных дисков</option>';
  }

  $("#btn-start-benchmark").addEventListener("click", async () => {
    const resultNode = $("#benchmark-result");
    resultNode.classList.add("hidden");
    const started = await run("Подготовка бенчмарка…", () => api("start_benchmark", Number($("#benchmark-duration").value), $("#benchmark-drive").value));
    if (!started) return;
    const status = await waitJob(started.job, () => {}, 700);
    if (status.status === "error") { toast(status.error || "Тест не удалось выполнить", true); return; }
    const result = status.result || {};
    const volume = result.volume || {};
    const seqRead = Number(result.seq_read) || 0;
    const seqWrite = Number(result.seq_write) || 0;
    const randomRead = Number(result.random_read) || 0;
    const randomWrite = Number(result.random_write) || 0;
    const volumeDetails = `${result.drive} · ${volume.label || "Локальный диск"} · ${volume.fs || "ФС н/д"} · ${fmtBytes(volume.size)} · свободно ${fmtBytes(volume.free)} (${volume.used_percent ?? "н/д"}% занято)`;
    resultNode.innerHTML = `<div class="benchmark-score">Результаты · ${esc(result.drive)} · ${esc(result.duration_seconds)} с</div><p class="muted small">${esc(volumeDetails)}</p><div class="benchmark-metrics"><div><small>Последовательное чтение · крупные файлы</small><strong>${esc(seqRead.toFixed(1))} МБ/с</strong><small>${esc((seqRead * 1.048576).toFixed(0))} МБ за 1 секунду*</small></div><div><small>Последовательная запись · крупные файлы</small><strong>${esc(seqWrite.toFixed(1))} МБ/с</strong><small>${esc((seqWrite * 1.048576).toFixed(0))} МБ за 1 секунду*</small></div><div><small>Случайное чтение · мелкие блоки</small><strong>${esc(randomRead.toFixed(1))} МБ/с</strong><small>Отклик на разрозненные операции</small></div><div><small>Случайная запись · мелкие блоки</small><strong>${esc(randomWrite.toFixed(1))} МБ/с</strong><small>Отклик на разрозненные операции</small></div></div><p class="muted small">${esc(result.method || "")}</p><p class="muted small">*Пересчёт скорости в объём за секунду, а не фактическое копирование. Результат не измеряет здоровье/износ накопителя и не гарантирует такую же скорость в играх или при копировании. Сравнивайте этот же диск при одинаковой нагрузке; разброс между прогонами нормален.</p>`;
    resultNode.classList.remove("hidden");
  });

  async function loadMaintenance() {
    await Promise.all([loadJunk(), loadDisk(), loadMeasurements()]);
  }

  async function loadJunk() {
    const data = await run("Список категорий…", () => api("junk_targets"));
    if (!data) return;
    renderJunk(data.targets);
  }

  function renderJunk(targets) {
    const container = el("#junk-list");
    if (!container) return;
    container.innerHTML = targets.map((item) => `
      <label class="junk-row ${riskClass(item.risk)}">
        <input type="checkbox" class="junk-check" value="${esc(item.id)}" ${junkChecked.has(item.id) ? "checked" : ""}>
        <div class="junk-main">
          <div class="junk-title">${esc(item.name)} ${riskBadge(item.risk)}</div>
          <div class="junk-sub muted small">${esc(item.description)}</div>
        </div>
        <div class="junk-size" data-size="${esc(item.id)}">${junkSizes[item.id] !== undefined ? fmtBytes(junkSizes[item.id]) : "—"}</div>
      </label>`).join("");

    container.querySelectorAll(".junk-check").forEach((box) => {
      box.addEventListener("change", () => {
        if (box.checked) junkChecked.add(box.value);
        else junkChecked.delete(box.value);
        updateJunkTotal();
      });
    });
    updateJunkTotal();
  }

  function riskClass(risk) {
    if (risk === "safe") return "is-safe";
    if (risk === "danger") return "is-danger";
    return "is-caution";
  }

  let activeDiagnosis = "startup";

  function renderDiagnostic() {
    const selected = DIAGNOSTICS.find((item) => item.id === activeDiagnosis) || DIAGNOSTICS[0];
    $("#diagnostic-symptoms").innerHTML = DIAGNOSTICS.map((item) =>
      `<button class="chip ${item.id === selected.id ? "is-active" : ""}" data-diagnostic="${item.id}" aria-pressed="${item.id === selected.id}">${esc(item.title)}</button>`
    ).join("");
    $("#diagnostic-content").innerHTML = `
      <h3>${esc(selected.heading)}</h3>
      <p class="muted small">${esc(selected.description)}</p>
      <ol>${selected.steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol>
      <div class="diagnostic-controls">
        ${selected.action === "ping" ? '<input class="input" id="diagnostic-host" type="text" maxlength="253" placeholder="IP или сервер, например 1.1.1.1" autocomplete="url">' : ""}
        <button class="btn" data-diagnose-action="${selected.action}">${esc(selected.button)}</button>
      </div>`;
    $("#diagnostic-result").classList.add("hidden");
    $("#diagnostic-result").textContent = "";
  }

  function showDiagnosticResult(text) {
    const result = $("#diagnostic-result");
    result.textContent = text;
    result.classList.remove("hidden");
  }

  $("#diagnostic-symptoms").addEventListener("click", (event) => {
    const button = event.target.closest("[data-diagnostic]");
    if (!button) return;
    activeDiagnosis = button.dataset.diagnostic;
    renderDiagnostic();
  });

  $("#diagnostic-content").addEventListener("click", async (event) => {
    const action = event.target.closest("[data-diagnose-action]")?.dataset.diagnoseAction;
    if (!action) return;

    if (action === "startup") {
      const data = await run("Замер загрузки и автозапуска…", () => api("take_measurement"));
      if (!data) return;
      const item = data.measurement || {};
      const boot = item.boot_ms == null ? "нет данных в журнале Windows" : `${(item.boot_ms / 1000).toFixed(1)} с`;
      const startup = item.startup == null ? "не удалось получить список" : `${item.startup} записей`;
      const processes = item.processes == null ? "н/д" : item.processes;
      let note = "Сравните этот результат со следующим замером после обычной перезагрузки.";
      if (item.boot_ms != null && item.boot_ms > 60000) note = "Последняя зарегистрированная загрузка заняла больше минуты; сравните повторные замеры — одно событие не выявляет причину.";
      else if (item.boot_ms != null && item.boot_ms < 20000) note = "Последняя зарегистрированная загрузка была короче 20 секунд. Если старт всё равно кажется долгим, сравните повторные замеры.";
      showDiagnosticResult(`Время загрузки: ${boot}\nАвтозапуск: ${startup}\nПроцессы сейчас: ${processes}\n\n${note}\nЗамер добавлен в историю «до / после».`);
      renderMeasurements(data.items || []);
      return;
    }

    if (action === "stutter") {
      const data = await run("Снимаю нагрузку 8 секунд… оставьте проблему активной", async () => {
        const samples = [];
        for (let index = 0; index < 6; index += 1) {
          updateBusyProgress(`Снимок нагрузки ${index + 1} из 6`, index * 100 / 6, `Сбор показателей · ${index + 1}/6`);
          samples.push(await api("get_metrics"));
          if (index < 5) await new Promise((resolve) => setTimeout(resolve, 1400));
        }
        updateBusyProgress("Обработка результатов замера", 100, "Завершаю…");
        return samples;
      });
      if (!data) return;
      const values = (key) => data.map((sample) => sample[key])
        .filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value)))
        .map(Number);
      const avg = (items) => items.length ? items.reduce((sum, value) => sum + value, 0) / items.length : null;
      const cpu = values("cpu");
      const ram = values("ram_percent");
      const cpuPeak = cpu.length ? Math.max(...cpu) : null;
      const ramAvg = avg(ram);
      const hints = [];
      if (cpuPeak !== null && cpuPeak >= 90) hints.push("CPU доходил до 90% или выше — проверьте, повторяется ли это во время проблемы.");
      if (ramAvg !== null && ramAvg >= 90) hints.push("В среднем было занято не менее 90% ОЗУ — нехватка памяти возможна.");
      if (!hints.length) hints.push("В коротком замере явной высокой загрузки CPU или памяти не обнаружено; повторите проверку во время микрофризов.");
      showDiagnosticResult(`Замеров: ${data.length}\nПиковая загрузка CPU: ${cpuPeak === null ? "н/д" : `${cpuPeak.toFixed(0)}%`}\nСредняя занятость ОЗУ: ${ramAvg === null ? "н/д" : `${ramAvg.toFixed(0)}%`}\n\n${hints.join("\n")}\nЭто не измерение FPS, времени кадра или input lag.`);
      return;
    }

    if (action === "ping") {
      const host = $("#diagnostic-host").value.trim();
      if (!host) { toast("Введите адрес игрового сервера или другой узел для проверки", true); return; }
      const data = await run(`Отправляю 4 ping-запроса на ${host}…`, () => api("ping_host", host));
      if (!data) return;
      const loss = Math.round(data.lost / data.sent * 100);
      const latency = data.avg_ms == null
        ? "Ответов нет. ICMP может быть закрыт на сервере или в сети."
        : `Задержка ответивших пакетов: минимум ${data.min_ms} мс, средняя ${data.avg_ms} мс, максимум ${data.max_ms} мс.`;
      showDiagnosticResult(`Узел: ${data.host}\nОтветы: ${data.received} из ${data.sent} · потери ${loss}%\n${latency}\n\nРезультат относится только к указанному узлу; игровой маршрут может отличаться.`);
      return;
    }

    if (action === "thermal") {
      const data = await run("Чтение доступного датчика…", () => api("get_metrics"));
      if (!data) return;
      const temp = data.temp == null ? "Windows не предоставила значение датчика." : `Доступный ACPI датчик: ${data.temp} °C.`;
      showDiagnosticResult(`${temp}\n\nПо этому показанию нельзя надёжно определить температуру CPU/GPU или подтвердить троттлинг. Для точного сравнения используйте утилиту производителя оборудования.`);
      return;
    }

    if (action === "disk") {
      const data = await run("Чтение состояния дисков и томов…", () => api("disk_info"));
      if (!data) return;
      const volumes = (data.volumes || []).map((volume) => {
        const freePercent = volume.size ? volume.free / volume.size * 100 : null;
        return `${volume.letter}: свободно ${fmtBytes(volume.free)}${freePercent === null ? "" : ` (${freePercent.toFixed(0)}%)`} из ${fmtBytes(volume.size)} · ${volume.health || "состояние н/д"}`;
      });
      const disks = (data.disks || []).map((disk) => `${disk.name}: ${disk.health || "SMART н/д"}${disk.temp == null ? "" : ` · ${disk.temp} °C`}${disk.wear == null ? "" : ` · износ ${disk.wear}%`}`);
      showDiagnosticResult(`${volumes.length ? volumes.join("\n") : "Сведения о томах недоступны."}\n\n${disks.length ? disks.join("\n") : "Сведения SMART недоступны."}\n\n«Н/д» означает, что Windows или драйвер не предоставили показатель; это не подтверждение неисправности.`);
      return;
    }

    if (action === "windows") {
      $("#repair-panel").scrollIntoView({ behavior: "smooth", block: "start" });
      toast("Выберите SFC или DISM ниже; команда запустится только после подтверждения.");
    }
  });

  renderDiagnostic();

  function updateJunkTotal() {
    const total = Array.from(junkChecked).reduce((sum, id) => sum + (junkSizes[id] || 0), 0);
    const node = el("#junk-total");
    if (!node) return;
    const known = Object.keys(junkSizes).length > 0;
    node.textContent = known
      ? `Выбрано ${junkChecked.size} категорий · ${fmtBytes(total)}`
      : "Нажмите «Сканировать», чтобы узнать размер";
  }

  async function scanJunk() {
    const data = await run("Сканирование мусора…", () => api("scan_junk"));
    if (!data) return;
    const status = await waitJob(data.job, () => {}, 900);
    if (status.status === "error") { toast(status.error || "Сканирование не удалось", true); return; }
    junkSizes = {};
    (status.result || []).forEach((item) => {
      if (item.size !== null && item.size !== undefined) junkSizes[item.id] = item.size;
    });
    renderJunk(status.result || []);
  }

  let jobProgressHideTimer = null;

  function renderJobProgress(status) {
    const panel = $("#job-progress");
    if (!panel) return;
    if (jobProgressHideTimer) clearTimeout(jobProgressHideTimer);
    jobProgressHideTimer = null;
    const running = status.status === "running";
    const done = status.status === "done";
    panel.classList.toggle("is-done", done);
    panel.classList.toggle("is-error", !running && !done);
    panel.classList.remove("hidden");
    $("#job-progress-title").textContent = status.title || "Задача";
    $("#job-progress-subtitle").textContent = running
      ? `Выполняется · прошло ${elapsedLabel(status.elapsed)}`
      : done ? "Завершено" : "Остановлено с ошибкой";
    $("#job-progress-state").textContent = running ? "В работе" : done ? "Готово" : "Ошибка";
    const lines = status.output || [];
    const detail = status.progress_message || lines[lines.length - 1] || (done ? "Операция завершена" : status.error || "Подготовка…");
    $("#job-progress-detail").textContent = detail;
    const track = $("#job-progress-track");
    const fill = $("#job-progress-fill");
    if (running && status.progress_percent !== null && status.progress_percent !== undefined && Number.isFinite(Number(status.progress_percent))) {
      track.classList.remove("is-indeterminate");
      fill.style.width = `${Math.max(0, Math.min(100, Number(status.progress_percent)))}%`;
    } else if (running) {
      track.classList.add("is-indeterminate");
      fill.style.width = "34%";
    } else {
      track.classList.remove("is-indeterminate");
      fill.style.width = done ? "100%" : `${Math.max(6, Math.min(100, Number(status.progress_percent) || 6))}%`;
      jobProgressHideTimer = setTimeout(() => panel.classList.add("hidden"), 2200);
    }
  }

  async function waitJob(jobId, onUpdate = () => {}, interval = 1200) {
    try {
      for (;;) {
        const status = await api("job_status", jobId);
        onUpdate(status);
        renderJobProgress(status);
        if (status.status !== "running") return status;
        await new Promise((resolve) => setTimeout(resolve, interval));
      }
    } catch (err) {
      const status = { title: "Фоновая задача", status: "error", error: err.message || String(err) };
      renderJobProgress(status);
      return status;
    }
  }

  async function cleanJunk() {
    const ids = Array.from(junkChecked);
    if (!ids.length) { toast("Выберите хотя бы одну категорию", true); return; }
    const dangerous = ids.includes("windows_old") || ids.includes("recycle");
    const ok = await confirmAction(
      "Очистить выбранное?",
      `Будут удалены: ${ids.map((id) => junkName(id)).join(", ")}.` +
        (dangerous ? "\n\nВнимание: корзина и Windows.old удаляются безвозвратно — восстановить файлы не получится." : ""),
      "Очистить",
      dangerous,
    );
    if (!ok) return;
    const data = await run("Запуск очистки…", () => api("clean_junk", ids));
    if (!data) return;
    const status = await waitJob(data.job, () => {}, 900);
    if (status.status === "error") { toast(status.error || "Очистка не удалась", true); return; }
    const result = status.result || { freed: 0, report: [] };
    const problems = (result.report || []).filter((item) => item.errors > 0);
    toast(`Освобождено ${fmtBytes(result.freed)}${problems.length ? `, предупреждений: ${problems.length}` : ""}`, problems.length > 0);
    await scanJunk();
  }

  function junkName(id) {
    const names = {
      temp: "временные файлы",
      thumbnails: "кэш эскизов",
      browsers: "кэш браузеров",
      recycle: "корзина",
      wu_download: "обновления Windows",
      windows_old: "Windows.old",
      dism: "компоненты DISM",
    };
    return names[id] || id;
  }

  async function loadDisk() {
    const data = await run("Чтение дисков…", () => api("disk_info"));
    if (!data) return;
    renderDisk(data);
  }

  function renderDisk(data) {
    const container = el("#disk-list");
    if (!container) return;
    const disks = data.disks || [];
    const volumes = data.volumes || [];
    const diskRows = disks.length ? disks.map((disk) => `
      <div class="disk-row">
        <div class="disk-main">
          <div class="disk-title">${esc(disk.name)} <span class="badge ${disk.ssd ? "badge-ok" : "badge-off"}">${esc(disk.media)}</span>
            <span class="badge ${disk.health === "Healthy" ? "badge-ok" : "badge-warn"}">${disk.health === "Healthy" ? "исправен" : esc(disk.health)}</span>
          </div>
          <div class="disk-sub muted small">
            ${esc(disk.bus || "")}${disk.temp !== null && disk.temp !== undefined ? ` · ${esc(disk.temp)}°C` : ""}
            ${disk.wear !== null && disk.wear !== undefined ? ` · износ ${esc(disk.wear)}%` : ""}
            ${disk.hours !== null && disk.hours !== undefined ? ` · ${esc(disk.hours)} ч` : ""}
          </div>
        </div>
        <span class="disk-size muted small">${fmtBytes(disk.size)}</span>
      </div>`).join("") : `<div class="muted small">Диски не найдены.</div>`;

    const volumeRows = volumes.map((volume) => `
      <div class="volume-row">
        <div class="volume-head">
          <strong>${esc(volume.letter)}:</strong>
          <span class="muted small">${esc(volume.label || volume.fs)} · свободно ${fmtBytes(volume.free)} из ${fmtBytes(volume.size)}</span>
        </div>
        <div class="meter"><span class="meter-fill" style="width:${Math.max(0, Math.min(100, volume.used_percent))}%"></span></div>
      </div>`).join("");

    container.innerHTML = `<div class="disk-list">${diskRows}</div>
      <div class="volume-list">${volumeRows || '<div class="muted small">Тома не найдены.</div>'}</div>`;

    const trimButton = el("#btn-trim");
    if (trimButton) {
      trimButton.disabled = !data.ssd_present;
      trimButton.title = data.ssd_present ? "TRIM для системного SSD" : "SSD не обнаружен";
    }
  }

  async function startRepair(kind) {
    const titles = { sfc: "Проверка системных файлов", dism: "Восстановление образа Windows" };
    const ok = await confirmAction(
      titles[kind],
      kind === "sfc"
        ? "Windows проверит целостность системных файлов и попробует восстановить повреждённые. Занимает 10–25 минут."
        : "DISM обратится к системному хранилищу компонентов и восстановит образ. Занимает 10–25 минут.",
      "Запустить",
      true,
    );
    if (!ok) return;
    const data = await run("Запуск проверки…", () => api("system_scan", kind));
    if (!data) return;
    const panel = el("#repair-status");
    const output = el("#repair-output");
    const title = el("#repair-title");
    const elapsed = el("#repair-elapsed");
    const spinner = el("#repair-spinner");
    if (panel) panel.classList.remove("hidden");
    if (title) title.textContent = data.title;
    if (output) output.textContent = "Ожидание вывода…";
    if (spinner) spinner.classList.remove("hidden");
    const started = Date.now();
    const timer = setInterval(() => {
      if (elapsed) elapsed.textContent = `${Math.round((Date.now() - started) / 1000)} с`;
    }, 1000);
    try {
      const status = await waitJob(data.job, (state) => {
        if (output) {
          output.textContent = (state.output || []).join("\n") || "Команда выполняется…";
          output.scrollTop = output.scrollHeight;
        }
      }, 1500);
      if (spinner) spinner.classList.add("hidden");
      if (title) title.textContent = `${data.title} — ${status.status === "done" ? "готово" : "ошибка"}`;
      if (output) output.textContent = (status.output || []).join("\n") || (status.error || "Нет вывода");
      toast(status.status === "done" ? "Проверка завершена" : (status.error || "Проверка завершилась с ошибкой"), status.status !== "done");
    } finally {
      clearInterval(timer);
    }
  }

  async function runTrim() {
    const ok = await confirmAction(
      "Выполнить TRIM?",
      "SSD получит команды на очистку неиспользуемых блоков. Данные не удаляются, операция безопасна и занимает несколько минут.",
      "Выполнить",
    );
    if (!ok) return;
    const data = await run("Запуск TRIM…", () => api("start_trim"));
    if (!data) return;
    const status = await waitJob(data.job, () => {}, 1200);
    toast(status.status === "done" ? "TRIM выполнен" : (status.error || "TRIM не удался"), status.status !== "done");
  }

  async function loadMeasurements() {
    const data = await run("Замеры…", () => api("list_measurements"));
    if (!data) return;
    renderMeasurements(data.items || []);
  }

  function deltaChip(value, unit, lowerIsBetter = true) {
    if (value === null || value === undefined) return '<span class="delta muted">—</span>';
    if (value === 0) return '<span class="delta">без изменений</span>';
    const good = lowerIsBetter ? value < 0 : value > 0;
    const sign = value > 0 ? "+" : "";
    return `<span class="delta ${good ? "is-good" : "is-bad"}">${sign}${Number(value).toFixed(unit === "мс" || unit === "шт" ? 0 : 1)} ${unit}</span>`;
  }

  function renderMeasurements(items) {
    const container = el("#measure-list");
    if (!container) return;
    if (!items.length) {
      container.innerHTML = '<div class="muted small">Замеров пока нет. Сделайте первый — он станет точкой отсчёта.</div>';
      return;
    }
    container.innerHTML = items.map((item) => {
      const boot = item.boot_ms !== null && item.boot_ms !== undefined ? `${(item.boot_ms / 1000).toFixed(1)} с` : "н/д";
      const delta = item.delta || {};
      return `
      <div class="measure-row">
        <div class="measure-main">
          <div class="measure-title">${fmtDate(item.created)}</div>
          <div class="measure-grid">
            <span>Процессов: <strong>${item.processes ?? "—"}</strong> ${delta.processes !== undefined && delta.processes !== null ? deltaChip(delta.processes, "шт") : ""}</span>
            <span>ОЗУ: <strong>${fmtGb(item.ram_used_mb)}</strong> ${delta.ram_used_mb ? deltaChip(delta.ram_used_mb, "МБ") : ""}</span>
            <span>Загрузка: <strong>${boot}</strong> ${delta.boot_ms ? deltaChip(delta.boot_ms, "мс") : ""}</span>
            <span>Автозапуск: <strong>${item.startup ?? "—"}</strong></span>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" data-del-measure="${esc(item.id)}">Удалить</button>
      </div>`;
    }).join("");
  }

  async function takeMeasurement() {
    const data = await run("Снимаю показатели…", () => api("take_measurement"));
    if (data) { toast("Замер сохранён"); loadMeasurements(); }
  }

  /* ---------- поиск ---------- */
  const TYPE_ICON = {
    view: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    tweak: '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h10M4 17h13"/><circle cx="19" cy="12" r="2"/></svg>',
    script: '<svg viewBox="0 0 24 24"><path d="M5 4h9l5 5v11H5z"/><path d="M14 4v5h5M8 13l2.5 2.5L8 18"/></svg>',
    tool: '<svg viewBox="0 0 24 24"><path d="M14.7 6.3a4 4 0 1 0 3 3L21 6l-3-3-3.3 3.3z"/><path d="M12.5 9.5 4 18l2 2 8.5-8.5"/></svg>',
  };
  const TYPE_RU = { view: "раздел", tweak: "твик", script: "скрипт", tool: "инструмент" };

  let searchItems = [];
  let searchCursor = 0;
  let searchTimer = null;
  let searchRequest = 0;

  function openSearch() {
    const overlay = el("#search-overlay");
    if (!overlay) return;
    overlay.classList.remove("hidden");
    const input = el("#search-input");
    if (input) {
      input.value = "";
      input.focus();
    }
    searchItems = [];
    searchCursor = 0;
    renderSearchResults([]);
  }

  function closeSearch() {
    const overlay = el("#search-overlay");
    if (overlay) overlay.classList.add("hidden");
  }

  function searchOpen() {
    const overlay = el("#search-overlay");
    return overlay && !overlay.classList.contains("hidden");
  }

  async function querySearch(text) {
    const query = text.trim();
    if (!query) { searchItems = []; renderSearchResults([]); return; }
    const token = ++searchRequest;
    try {
      const data = await api("global_search", query);
      if (token !== searchRequest) return;
      searchItems = data.items || [];
      searchCursor = 0;
      renderSearchResults(searchItems, query);
    } catch (err) {
      if (token === searchRequest) renderSearchResults([], query, err.message);
    }
  }

  function renderSearchResults(items, query = "", error = "") {
    const container = el("#search-results");
    if (!container) return;
    if (error) {
      container.innerHTML = `<div class="search-empty muted">${esc(error)}</div>`;
      return;
    }
    if (!query) {
      container.innerHTML = `<div class="search-hint muted small">Начните вводить название твика, скрипта или инструмента. Поиск понимает опечатки и неправильную раскладку.</div>`;
      return;
    }
    if (!items.length) {
      container.innerHTML = `<div class="search-empty muted">Ничего не найдено по запросу «${esc(query)}»</div>`;
      return;
    }
    container.innerHTML = items.map((item, index) => `
      <button class="search-item ${index === searchCursor ? "is-active" : ""}" data-index="${index}">
        <span class="search-icon">${TYPE_ICON[item.type] || TYPE_ICON.view}</span>
        <span class="search-text">
          <span class="search-title">${esc(item.title)}</span>
          <span class="search-sub muted">${esc(item.subtitle || "")}</span>
        </span>
        <span class="search-type muted small">${TYPE_RU[item.type] || ""}</span>
      </button>`).join("");
  }

  function moveSearch(delta) {
    if (!searchItems.length) return;
    searchCursor = (searchCursor + delta + searchItems.length) % searchItems.length;
    renderSearchResults(searchItems, el("#search-input").value);
    const active = el("#search-results .search-item.is-active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  function openSearchResult(item) {
    if (!item) return;
    closeSearch();
    if (item.type === "tweak") {
      state.category = item.category || state.category;
      state.search = "";
      if (el("#tweak-search")) el("#tweak-search").value = "";
      setView("registry");
      setTimeout(() => {
        const card = document.querySelector(`#tweak-list .card[data-id="${item.id}"]`);
        if (card) {
          card.scrollIntoView({ block: "center", behavior: "smooth" });
          state.flash.set(item.id, true);
          renderTweaks();
        }
      }, 320);
      return;
    }
    if (item.type === "script") {
      setView("scripts");
      setTimeout(() => {
        const search = el("#script-search");
        if (search) { search.value = item.query || item.title; renderScripts(); }
      }, 320);
      return;
    }
    setView(item.view || "dashboard");
  }

  if (el("#btn-search")) el("#btn-search").addEventListener("click", openSearch);
  if (el("#search-close")) el("#search-close").addEventListener("click", closeSearch);
  if (el("#search-overlay")) {
    el("#search-overlay").addEventListener("click", (event) => {
      if (event.target === el("#search-overlay")) closeSearch();
    });
  }
  if (el("#search-input")) {
    el("#search-input").addEventListener("input", (event) => {
      clearTimeout(searchTimer);
      const value = event.target.value;
      searchTimer = setTimeout(() => querySearch(value), 140);
    });
    el("#search-input").addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") { event.preventDefault(); moveSearch(1); }
      else if (event.key === "ArrowUp") { event.preventDefault(); moveSearch(-1); }
      else if (event.key === "Enter") { event.preventDefault(); openSearchResult(searchItems[searchCursor]); }
      else if (event.key === "Escape") { event.preventDefault(); closeSearch(); }
    });
  }
  if (el("#search-results")) {
    el("#search-results").addEventListener("click", (event) => {
      const button = event.target.closest("[data-index]");
      if (!button) return;
      openSearchResult(searchItems[Number(button.dataset.index)]);
    });
  }

  document.addEventListener("keydown", (event) => {
    const hotkey = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
    if (hotkey) { event.preventDefault(); searchOpen() ? closeSearch() : openSearch(); }
    else if (event.key === "Escape" && searchOpen()) closeSearch();
  });

  /* ---------- тур ---------- */
  const TOUR = [
    {
      view: "dashboard",
      title: "Обзор",
      text: "Сводные карточки системы наверху, мониторинг процессора, памяти, видеокарты и температуры — ниже. Опрос идёт раз в 1,5 секунды.",
    },
    {
      view: "registry",
      title: "Реестр",
      text: "25 проверенных настроек по категориям. Карточка показывает состояние, риск и кнопку «Подробнее» с ключом и значениями. Перед каждым изменением делается .reg-бэкап.",
    },
    {
      view: "telemetry",
      title: "Телеметрия",
      text: "Одна кнопка активирует ограничения Windows, Microsoft Office, Edge и установленных браузеров. DiagTrack останавливается и отключается; тип запуска и состояние службы сохраняются для точного отката. Defender и Windows Update не отключаются.",
    },
    {
      view: "scripts",
      title: "Мои скрипты",
      text: "Все материалы из исходной папки: .reg, .bat, .cmd, .ps1. Приложение само определяет, что уже выполнено, и умеет откатывать изменения.",
    },
    {
      view: "maintenance",
      title: "Обслуживание",
      text: "Очистка мусора с предпросмотром размера, SMART и TRIM, sfc / DISM одной кнопкой и замеры «до/после».",
    },
  ];
  let tourStep = 0;

  function highlightTour(view) {
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.classList.toggle("tour-target", btn.dataset.view === view);
    });
  }

  function renderTour() {
    const step = TOUR[tourStep];
    if (!step) return finishTour();
    if (el("#tour-step")) el("#tour-step").textContent = `${tourStep + 1} / ${TOUR.length}`;
    if (el("#tour-title")) el("#tour-title").textContent = step.title;
    if (el("#tour-text")) el("#tour-text").textContent = step.text;
    if (el("#tour-next")) el("#tour-next").textContent = tourStep === TOUR.length - 1 ? "Готово" : "Далее";
    if (el("#tour-prev")) el("#tour-prev").disabled = tourStep === 0;
    highlightTour(step.view);
    setView(step.view);
  }

  function startTour(index = 0) {
    tourStep = index;
    if (el("#tour")) el("#tour").classList.remove("hidden");
    renderTour();
  }

  function finishTour() {
    if (el("#tour")) el("#tour").classList.add("hidden");
    document.querySelectorAll(".nav-item").forEach((btn) => btn.classList.remove("tour-target"));
    run("Сохранение…", async () => { await api("finish_onboarding"); return true; });
  }

  if (el("#tour-next")) {
    el("#tour-next").addEventListener("click", () => {
      if (tourStep >= TOUR.length - 1) return finishTour();
      tourStep += 1;
      renderTour();
    });
  }
  if (el("#tour-prev")) {
    el("#tour-prev").addEventListener("click", () => {
      if (tourStep === 0) return;
      tourStep -= 1;
      renderTour();
    });
  }
  if (el("#tour-skip")) el("#tour-skip").addEventListener("click", finishTour);

  /* ---------- обработчики обслуживания ---------- */
  if (el("#btn-scan-junk")) el("#btn-scan-junk").addEventListener("click", scanJunk);
  if (el("#btn-clean-junk")) el("#btn-clean-junk").addEventListener("click", cleanJunk);
  if (el("#btn-refresh-disk")) el("#btn-refresh-disk").addEventListener("click", loadDisk);
  if (el("#btn-trim")) el("#btn-trim").addEventListener("click", runTrim);
  if (el("#btn-sfc")) el("#btn-sfc").addEventListener("click", () => startRepair("sfc"));
  if (el("#btn-dism")) el("#btn-dism").addEventListener("click", () => startRepair("dism"));
  if (el("#btn-measure")) el("#btn-measure").addEventListener("click", takeMeasurement);
  if (el("#btn-tour-again")) el("#btn-tour-again").addEventListener("click", () => startTour(0));
  if (el("#measure-list")) {
    el("#measure-list").addEventListener("click", async (event) => {
      const id = event.target.closest("[data-del-measure]")?.dataset.delMeasure;
      if (!id) return;
      const ok = await confirmAction("Удалить замер?", "Запись исчезнет из истории. Система не меняется.", "Удалить");
      if (!ok) return;
      const data = await run("Удаление…", () => api("delete_measurement", id));
      if (data) { toast("Замер удалён"); loadMeasurements(); }
    });
  }

  async function boot() {
    const info = await run("Подключение к backend…", () => api("get_system_info"));
    if (info) {
      state.admin = info.admin;
      state.system = info;
      renderAdmin(info.admin);
      $("#side-version").textContent = `v${info.app_version}`;
      const settings = await run("Настройки…", () => api("get_settings"));
      if (settings) state.settings = settings;
    }
    loadDashboard();
    startMonitor();
    if (state.settings && !state.settings.onboarding_done) {
      setTimeout(() => startTour(0), 700);
    }
  }

  if (window.pywebview && window.pywebview.api) {
    boot();
  } else {
    window.addEventListener("pywebviewready", boot, { once: true });
  }
})();

