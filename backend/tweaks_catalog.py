"""Каталог твиков реестра, собранный из папки «оптимизация».

Каждая запись описывает одно значение реестра. Дубли из исходных .reg/.bat
объединены, опасные и некорректные настройки исключены из каталога.
"""
from __future__ import annotations

CATEGORIES = [
    {"id": "performance", "name": "Производительность"},
    {"id": "privacy", "name": "Приватность"},
    {"id": "network", "name": "Сеть"},
    {"id": "explorer", "name": "Проводник"},
    {"id": "games", "name": "Игры"},
    {"id": "system", "name": "Система"},
    {"id": "graphics", "name": "Видеокарта"},
]

RISK_LABELS = {"safe": "безопасно", "caution": "осторожно", "danger": "опасно"}

_HKLM = "HKEY_LOCAL_MACHINE"
_HKCU = "HKEY_CURRENT_USER"

def _tweak(
    tid: str,
    name: str,
    description: str,
    category: str,
    key_path: str,
    value_name: str,
    on_value,
    off_value,
    risk: str = "caution",
    value_type: str = "REG_DWORD",
    restart: bool = False,
    source: str = "",
) -> dict:
    return {
        "id": tid,
        "name": name,
        "description": description,
        "category": category,
        "key_path": key_path,
        "value_name": value_name,
        "value_type": value_type,
        "on_value": on_value,
        "off_value": off_value,
        "risk": risk,
        "requires_admin": key_path.upper().startswith(("HKLM", "HKEY_LOCAL_MACHINE")),
        "restart": restart,
        "source": source,
    }


TWEAKS = [
    _tweak(
        "power_throttling_off",
        "Отключить Power Throttling",
        "Windows искусственно замедляет фоновые процессы ради экономии энергии. "
        "Отключение даёт им полную частоту CPU — полезно для игр и рендера, на ноутбуке быстрее садится батарея.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling",
        "PowerThrottlingOff", 1, 0, "caution",
        source="Disable Power Throttling.reg, Power Optimization.reg, 1 Power Throttling.reg",
    ),
    _tweak(
        "system_responsiveness",
        "Отзывчивость системы",
        "Доля процессорного времени, которую Windows резервирует под фоновые задачи, — в процентах. "
        "0 отдаёт приоритет активной программе (игре), фону остаётся минимум.",
        "performance",
        r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
        "SystemResponsiveness", 0, 20, "caution",
        source="CPU Optimization.reg",
    ),
    _tweak(
        "win32_priority",
        "Приоритет потоков игр (26)",
        "Кванты планировщика: короткий квант = быстрее реакция игры, длинный = стабильнее фон. "
        "26 (0x26) — сбалансированный вариант из исходного пакета без микропросадок FPS.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl",
        "Win32PrioritySeparation", 0x26, 2, "caution",
        restart=True,
        source="Win32PrioritySeparation - 26 Normal.reg, +fps.reg",
    ),
    _tweak(
        "paging_executive",
        "Держать ядро в памяти",
        "Запрещает выгружать код ядра и драйверов в файл подкачки. Меньше обращений к диску, "
        "но чуть больше занятой ОЗУ (актуально при 8 ГБ и меньше).",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "DisablePagingExecutive", 1, 0, "caution",
        restart=True,
        source="Драйвера и ядро загрузка в озу.reg, Memory Management Optimizations.reg",
    ),
    _tweak(
        "distribute_timers",
        "Распределение таймеров по ядрам",
        "Разносит таймеры ядра по процессорам, снижая нагрузку на одно ядро. "
        "Может помочь при микрофризах, но эффект зависит от железа.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
        "DistributeTimers", 1, 0, "caution",
        restart=True,
        source="Distribute Timers.reg",
    ),
    _tweak(
        "boost_priority",
        "BoostPriority планировщика",
        "Разрешает планировщику временно повышать приоритет потока, которому не хватает CPU. "
        "Ускоряет отклик интерфейса под нагрузкой.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Executive",
        "BoostPriority", 1, 0, "caution",
        restart=True,
        source="BoostPriority.reg",
    ),
    _tweak(
        "power_event_processor",
        "Отключить обработчик событий питания",
        "Отключает фоновый разбор событий управления питанием — меньше прерываний и работы ядра. "
        "Не влияет на сон/выключение, только на сбор статистики.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Power",
        "EventProcessorEnabled", 0, 1, "caution",
        restart=True,
        source="4 Disable Event Processor.reg, 1 Power.reg",
    ),
    _tweak(
        "energy_estimation",
        "Отключить оценку энергопотребления",
        "Windows перестаёт считать прогноз расхода энергии в фоне. Чистая экономия ресурсов, "
        "но график энергопотребления в настройках станет пустым.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Power",
        "EnergyEstimationEnabled", 0, 1, "safe",
        source="1 Power.reg",
    ),
    _tweak(
        "usb_selective_suspend",
        "Не отключать USB-порты для экономии",
        "Запрещает Windows усыплять USB-устройства. Убирает подвисания мыши, клавиатуры и звуковых карт "
        "после простоя; на ноутбуке немного повышает расход батареи.",
        "performance",
        r"HKLM\SYSTEM\CurrentControlSet\Services\USB",
        "DisableSelectiveSuspend", 1, 0, "safe",
        restart=True,
        source="2 USB Suspend Disable.reg",
    ),

    _tweak(
        "network_throttling",
        "Снять сетевой троттлинг",
        "Меняет NetworkThrottlingIndex в профиле мультимедийного планировщика Windows. "
        "Влияние на игры и ping зависит от системы и обычно не гарантировано; сравните замеры до и после.",
        "network",
        r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
        "NetworkThrottlingIndex", 0xFFFFFFFF, 10, "safe",
        source="CPU Optimization.reg",
    ),

    _tweak(
        "background_apps",
        "Запретить фоновые приложения",
        "Магазинные приложения больше не работают в фоне: не грузят диск, сеть и ОЗУ. "
        "Уведомления от них приходить не будут.",
        "privacy",
        r"HKCU\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
        "GlobalUserDisabled", 1, 0, "safe",
        source="Global User Disabled.reg",
    ),

    _tweak(
        "menu_show_delay",
        "Ускорить открытие меню Проводника",
        "Ставит MenuShowDelay в 0 мс вместо стандартных 400 мс: контекстные меню Windows раскрываются быстрее. "
        "Это только задержка показа меню, она не снижает input lag, ping или время кадра. "
        "Кнопка отката задаёт стандартные 400 мс. «Отменить последнее» восстанавливает значение, которое было до включения этого твика.",
        "explorer",
        r"HKCU\Control Panel\Desktop",
        "MenuShowDelay", "0", "400", "safe", value_type="REG_SZ",
        restart=True,
        source="Desktop tweaks.reg",
    ),

    _tweak(
        "gamedvr_off",
        "Отключить Game DVR",
        "Фоновая запись игрового процесса через GameConfigStore. Забирает часть FPS и дискового ввода-вывода.",
        "games",
        r"HKCU\System\GameConfigStore",
        "GameDVR_Enabled", 0, 1, "caution",
        source="Exclusive_Fullscreen.reg, GameBar, GameDVR.reg, FSE and Game Bar off.bat",
    ),
    _tweak(
        "game_capture",
        "Отключить запись игр",
        "Запрещает Xbox Game Bar захватывать экран и звук. Освобождает ресурсы, но функция записи клипов пропадёт.",
        "games",
        r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
        "AppCaptureEnabled", 0, 1, "caution",
        source="Exclusive_Fullscreen.reg, GameBar, GameDVR.reg, FSE and Game Bar off.bat",
    ),
    _tweak(
        "auto_game_mode",
        "Отключить авто-режим игры",
        "Windows перестаёт сам включать Game Mode, который иногда снижает FPS в соревновательных играх.",
        "games",
        r"HKCU\SOFTWARE\Microsoft\GameBar",
        "AutoGameModeEnabled", 0, 1, "safe",
        source="Exclusive_Fullscreen.reg, GameBar, GameDVR.reg",
    ),
    _tweak(
        "gamebar_startup",
        "Убрать панель Game Bar при запуске",
        "Отключает стартовую панель и подсказки Xbox Game Bar, которые всплывают поверх игры.",
        "games",
        r"HKCU\SOFTWARE\Microsoft\GameBar",
        "ShowStartupPanel", 0, 1, "safe",
        source="Exclusive_Fullscreen.reg, GameBar, GameDVR.reg",
    ),
    _tweak(
        "games_priority",
        "Приоритет игр в планировщике",
        "Повышает приоритет игровых потоков в профиле мультимедиа `Tasks\\Games` (по умолчанию 2). "
        "Игра получает больше времени CPU, фон — меньше.",
        "games",
        r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
        "Priority", 6, 2, "safe",
        source="Game Optimizations.reg",
    ),
    _tweak(
        "games_sfio",
        "Высокий SFIO-приоритет игр",
        "Повышает приоритет файлового ввода-вывода игровых процессов — быстрее подгрузка текстур.",
        "games",
        r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games",
        "SFIO Priority", "High", "Normal", "safe", value_type="REG_SZ",
        source="Game Optimizations.reg, Boost FPS .reg",
    ),

    _tweak(
        "hibernate_off",
        "Отключить гибернацию",
        "Освобождает hiberfil.sys (до нескольких ГБ на диске) и убирает пункт «Гибернация» из меню питания. "
        "Быстрый запуск Windows тоже отключается — включите твик обратно, если он нужен.",
        "system",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Power",
        "HibernateEnabled", 0, 1, "safe",
        source="Отключить гибернация.reg",
    ),
    _tweak(
        "wu_driver_updates",
        "Не искать драйверы в Windows Update",
        "Запрещает подменять драйверы устройств версиями из Windows Update. "
        "Полезно после установки свежего драйвера видеокарты; сама Windows продолжает обновляться.",
        "system",
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\DriverSearching",
        "DontSearchWindowsUpdate", 1, 0, "safe",
        restart=True,
        source="Выключить автообновление драйверов.reg",
    ),
    _tweak(
        "auto_end_tasks",
        "Автозавершение зависших программ",
        "При выходе из системы Windows сама закрывает зависшие приложения, не показывая диалог ожидания.",
        "system",
        r"HKCU\Control Panel\Desktop",
        "AutoEndTasks", "1", "0", "safe", value_type="REG_SZ",
        source="Desktop tweaks.reg",
    ),
    _tweak(
        "hung_app_timeout",
        "Быстрый таймаут «не отвечает»",
        "Через 1 секунду без ответа программа считается зависшей (по умолчанию 5 секунд). "
        "Интерфейс реже замирает на ожидании.",
        "system",
        r"HKCU\Control Panel\Desktop",
        "HungAppTimeout", "1000", "5000", "safe", value_type="REG_SZ",
        source="Desktop tweaks.reg",
    ),
    _tweak(
        "wait_to_kill_timeout",
        "Быстрое закрытие при выходе",
        "Даёт приложениям 2 секунды на корректное завершение вместо 20. Выход из системы заметно быстрее, "
        "но программа может не успеть сохранить черновик.",
        "system",
        r"HKCU\Control Panel\Desktop",
        "WaitToKillAppTimeout", "2000", "20000", "safe", value_type="REG_SZ",
        source="Desktop tweaks.reg",
    ),

    _tweak(
        "gpu_per_core_dpc",
        "AMD/NVIDIA: DPC видеодрайвера по каждому ядру",
        "Общий параметр драйвера AMD или NVIDIA: разрешает обрабатывать прерывания на всех ядрах CPU, а не на одном. "
        "Снижает микрофризы; поддерживается драйверами NVIDIA/AMD не на всех системах.",
        "graphics",
        r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        "RmGpsPsEnablePerCpuCoreDpc", 1, 0, "caution",
        restart=True,
        source="GPU Tweaks.reg, Rm Gps Ps Enable Per Cpu Core Dpc.reg",
    ),
    _tweak(
        "amd_ulps_off",
        "AMD: отключить ULPS",
        "Ultra Low Power State усыпляет вторую видеокарту/GPU и вызывает микроподвисания в CrossFire. "
        "Доступно только на системах с AMD-драйвером.",
        "graphics",
        r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000",
        "EnableUlps", 0, 1, "caution",
        restart=True,
        source="Disable Some Power Savings.reg",
    ),
]

TWEAKS_BY_ID = {tweak["id"]: tweak for tweak in TWEAKS}


def tweak_by_id(tweak_id: str) -> dict:
    tweak = TWEAKS_BY_ID.get(tweak_id)
    if tweak is None:
        raise ValueError(f"Неизвестный твик: {tweak_id}")
    return tweak
