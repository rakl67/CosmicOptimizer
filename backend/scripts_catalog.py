"""Описание всех материалов из папки «оптимизация», перенесённых в scripts/материалы/.

Файлы лежат рядом с приложением и запускаются только вручную кнопкой «Выполнить».
Пометка «опасно» — честное предупреждение, а не запрет: решение за пользователем.
"""
from __future__ import annotations

_BASE = "материалы/"

SCRIPTS = {
    "CPU Optimization Pack/CPU Optimizations/CPU Optimization.reg": {
        "title": "CPU: сетевой троттлинг + отзывчивость",
        "description": "NetworkThrottlingIndex=ffffffff и SystemResponsiveness=0. Ниже пинг, приоритет активной программе. "
                       "Часть значений уже есть отдельным безопасным твиком в разделе «Реестр».",
        "risk": "caution",
    },
    "CPU Optimization Pack/CPU Optimizations/Disable Power Throttling.reg": {
        "title": "CPU: отключить Power Throttling",
        "description": "PowerThrottlingOff=1. Фоновые процессы перестают замедляться ради экономии энергии. "
                       "Дублируется твиком «Отключить Power Throttling».",
        "risk": "caution",
    },
    "CPU Optimization Pack/CPU Optimizations/Game Optimizations.reg": {
        "title": "CPU: профиль игр в планировщике",
        "description": "Профиль Tasks\\Games: GPU Priority, Priority, Scheduling Category, SFIO Priority. "
                       "Встроено в «Реестр → Игры» два твика.",
        "risk": "safe",
    },
    "CPU Optimization Pack/CPU Optimizations/Power Optimization.reg": {
        "title": "CPU: Power Throttling + шаблоны схем питания",
        "description": "Кроме PowerThrottlingOff правит DefaultPowerSchemeValues трёх схем питания. "
                       "Значения шаблонов применяются только к новым схемам.",
        "risk": "caution",
    },

    "FPS Pack/Reg Tweaks/Decrease Delay.reg": {
        "title": "FPS: «уменьшение задержек» SMB",
        "description": "Правит SMB-сервер: EnableOplocks=0, autodisconnect, IRPStackSize. "
                       "На FPS не влияет, зато замедляет сетевые файловые операции и ломает oplocks. Не рекомендуется.",
        "risk": "danger",
    },
    "FPS Pack/Reg Tweaks/GPU Tweaks.reg": {
        "title": "FPS: DPC видеодрайвера по ядрам",
        "description": "RmGpsPsEnablePerCpuCoreDpc=1 в пяти ветках GraphicsDrivers. Встроено одним твиком в «Видеокарту».",
        "risk": "caution",
    },
    "FPS Pack/Reg Tweaks/Memory Management Optimizations.reg": {
        "title": "FPS: «оптимизация памяти» (20 значений)",
        "description": "Кроме DisablePagingExecutive отключает SEHOP, CFG и mitigations Spectre/Meltdown, меняет размеры пулов. "
                       "Снижает защиту системы без выигрыша в FPS. Не рекомендуется.",
        "risk": "danger",
    },

    "Optimization BAT and CMD/3. Remove Power Saving Features On USB Devices.bat": {
        "title": "USB: снять экономию энергии с устройств",
        "description": "Через SetACL меняет владельцев ключей Device Parameters у каждого USB-устройства. "
                       "Путь C:\\Windows\\SetACL.exe в системе отсутствует, откат не предусмотрен. "
                       "Безопасная замена — твик «Не отключать USB-порты для экономии».",
        "risk": "danger",
    },
    "Optimization BAT and CMD/BCDEdit Tweaks.cmd": {
        "title": "Ядро: disabledynamictick + useplatformtick",
        "description": "Переводит систему на платформенный таймер. Требует перезагрузки, откат — bcdedit /deletevalue. "
                       "На ноутбуках повышает расход батареи.",
        "risk": "caution",
        "restart": True,
        "undo": "bcdedit /deletevalue disabledynamictick & bcdedit /deletevalue useplatformtick",
        "undo_label": "Вернуть динамический тик",
    },
    "Optimization BAT and CMD/Enble ECN Capability.bat": {
        "title": "Сеть: включить ECN",
        "description": "netsh int tcp set global ecncapability=enabled. На Win10/11 ECN управляется автоматически; "
                       "принудительное включение может ломать старые роутеры и VPN.",
        "risk": "caution",
    },
    "Optimization BAT and CMD/FSE and Game Bar off.bat": {
        "title": "Игры: FSE, Game Bar и Game DVR (батник)",
        "description": "20 команд reg add для GameBar/GameDVR и удаление двух подключей Children/Parents. "
                       "Встроено без удаления ключей — четыре твика в «Реестр → Игры».",
        "risk": "caution",
    },

    "ЕСЛИ ПРОБЛЕМЫ С [faceit]/Faceit AC/2 - EnableMemoryIntegrity.ps1": {
        "title": "FACEIT: включить Memory Integrity (HVCI/VBS)",
        "description": "Включает Hyper-V, VBS и hvservice, затем ПЕРЕЗАГРУЖАЕТ компьютер без запроса. "
                       "Может сломать эмуляторы, виртуалки и часть античитов. Запускать только осознанно.",
        "risk": "danger",
        "restart": True,
    },
    "ЕСЛИ ПРОБЛЕМЫ С [faceit]/Включить DEP Защиту.bat": {
        "title": "FACEIT: вернуть защиту DEP",
        "description": "bcdedit /set {current} nx AlwaysOn — восстанавливает DEP после античитов. Нужна перезагрузка.",
        "risk": "safe",
        "restart": True,
        "undo": "bcdedit /set {current} nx OptIn",
        "undo_label": "Вернуть DEP в режим OptIn",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/1 Power Throttling.reg": {
        "title": "Питание: Power Throttling off (дубль)",
        "description": "PowerThrottlingOff=1. Полный дубль других файлов, оставлен для совместимости с оригинальной папкой.",
        "risk": "caution",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/2 Открывать pow файлы.reg": {
        "title": "Ассоциация .pow → powercfg",
        "description": "Открывает файлы схем электропитания импортом через powercfg. Не оптимизация, просто удобство.",
        "risk": "safe",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/4 Disable Event Processor.reg": {
        "title": "Питание: отключить обработчик событий",
        "description": "EventProcessorEnabled=0 — меньше фоновой работы ядра. Встроено в «Реестр → Производительность».",
        "risk": "caution",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/BoostPriority.reg": {
        "title": "Планировщик: BoostPriority",
        "description": "Временное повышение приоритета потока, которому не хватает CPU. Встроено в «Реестр».",
        "risk": "caution",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/Desktop tweaks.reg": {
        "title": "Проводник: меню, таймауты, автозавершение",
        "description": "AutoEndTasks, HungAppTimeout, WaitToKillAppTimeout, MenuShowDelay, LowLevelHooksTimeout. "
                       "Первые четыре встроены в «Реестр → Проводник/Система».",
        "risk": "safe",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/Distribute Timers.reg": {
        "title": "Ядро: DistributeTimers",
        "description": "Разносит таймеры по ядрам. Встроено в «Реестр → Производительность».",
        "risk": "caution",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/Exclusive_Fullscreen.reg": {
        "title": "Игры: эксклюзивный полный экран + GameDVR",
        "description": "GameConfigStore, GameDVR и политика GameBar. Встроено четырьмя твиками в «Реестр → Игры».",
        "risk": "caution",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/Global User Disabled.reg": {
        "title": "Приватность: запрет фоновых приложений",
        "description": "GlobalUserDisabled=1 в BackgroundAccessApplications. Встроено в «Реестр → Приватность».",
        "risk": "safe",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/MaxProcessCount.reg": {
        "title": "LSA: MaxProcessCount = 0x41ff",
        "description": "Меняет недокументированный лимит процессов LSA. К производительности отношения не имеет, "
                       "может упереться в потолок под нагрузкой. Требует перезагрузки.",
        "risk": "danger",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/QueueDepth.reg": {
        "title": "Диск: storahci QueueDepth = 50",
        "description": "Ручная глубина очереди AHCI. На NVMe не применяется, на SATA может уронить стабильность. "
                       "Перезагрузка обязательна.",
        "risk": "danger",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/SystemProfile Low Latency.reg": {
        "title": "SystemProfile: «низкая задержка»",
        "description": "MaxFrameLatency, IdleDisableOverride, Affinity Policy, Background Processing Priority. "
                       "Значения недокументированы, могут вызывать фризы в MMCS.",
        "risk": "danger",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/SystemProfile Timer.reg": {
        "title": "SystemProfile: «таймеры» (не работают)",
        "description": "HighPrecisionTimer, HighResolutionEventTimer, LatencyTimer — таких значений в Win10/11 нет. "
                       "Файл ничего не меняет, оставлен для полноты.",
        "risk": "danger",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/ToggleKeys.reg": {
        "title": "Спец. возможности: ToggleKeys/StickyKeys",
        "description": "Меняет флаги залипания клавиш и фильтрации ввода. Можно потерять управление клавиатурой. "
                       "Не оптимизация.",
        "risk": "danger",
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/Драйвера и ядро загрузка в озу.reg": {
        "title": "Ядро: держать в памяти (DisablePagingExecutive)",
        "description": "Запрещает выгружать код ядра в подкачку. Встроено в «Реестр → Производительность».",
        "risk": "caution",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/ТЕСТИМ/Win32PrioritySeparation - 26 Normal.reg": {
        "title": "Планировщик: Win32PrioritySeparation = 26",
        "description": "Сбалансированный вариант (0x26). Именно он встроен в приложение как основной твик.",
        "risk": "caution",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/ТЕСТИМ/Win32PrioritySeparation - 28 Best FPS.reg": {
        "title": "Планировщик: Win32PrioritySeparation = 28",
        "description": "Альтернатива «для FPS» (0x28). Конфликтует с вариантом 26 — применять только один из них.",
        "risk": "caution",
        "restart": True,
    },
    "ОСНОВЫ ВИНДЫ/РЕГИ/ТЕСТИМ/Win32PrioritySeparation - Best Latency.reg": {
        "title": "Планировщик: Win32PrioritySeparation = 0xffff3f91",
        "description": "Экспериментальное значение «лучшая задержка». Конфликтует с 26 и 28.",
        "risk": "danger",
        "restart": True,
    },

    "ПРОСТО ПОЛЕЗНОЕ/BAT ПОЛЕЗНОЕ/Отключить обновления Windows.bat": {
        "title": "Windows Update: отключить полностью",
        "description": "Останавливает wuauserv, UsoSvc, BITS, ставит Start=4, отключает задачи и УДАЛЯЕТ "
                       "C:\\Windows\\SoftwareDistribution. Ломает обновления Windows и Defender, откат вручную. "
                       "Не рекомендуется.",
        "risk": "danger",
        "restart": True,
    },
    "ПРОСТО ПОЛЕЗНОЕ/REG ПОЛЕЗНОЕ/1 Power.reg": {
        "title": "Питание: EnergyEstimation + EventProcessor",
        "description": "EnergyEstimationEnabled=0 и EventProcessorEnabled=0. Оба встроены в «Реестр → Производительность».",
        "risk": "caution",
    },
    "ПРОСТО ПОЛЕЗНОЕ/REG ПОЛЕЗНОЕ/2 USB Suspend Disable.reg": {
        "title": "USB: DisableSelectiveSuspend (безопасный вариант)",
        "description": "Один ключ Services\\USB вместо правки владельцев устройств. Встроено в «Реестр → Производительность».",
        "risk": "safe",
    },
    "ПРОСТО ПОЛЕЗНОЕ/REG ПОЛЕЗНОЕ/3 EnableLegacyDetection.reg": {
        "title": "Ввод: отключить legacy-детект PS/2",
        "description": "i8042prt: EnableWheelDetection=0, EnableLegacyDetection=0. На части ПК пропадает мышь/клавиатура "
                       "после загрузки. Не рекомендуется.",
        "risk": "danger",
        "restart": True,
    },
    "ПРОСТО ПОЛЕЗНОЕ/REG ПОЛЕЗНОЕ/Выключить автообновление драйверов.reg": {
        "title": "Драйверы: не искать в Windows Update",
        "description": "ExcludeWUDriversInQualityUpdate + DriverSearching. Встроено в «Реестр → Система» одним твиком.",
        "risk": "safe",
    },

    "Реестр/+fps.reg": {
        "title": "FPS: Win32PrioritySeparation (дубль)",
        "description": "Значение 26, полный дубль файла «Win32PrioritySeparation - 26 Normal.reg».",
        "risk": "caution",
        "restart": True,
    },
    "Реестр/Отключить UAC.reg": {
        "title": "UAC: отключить контроль учётных записей",
        "description": "EnableLUA=0 и сопутствующие политики. Любая программа получает админ-права без запроса. "
                       "Прямое снижение безопасности, откат требует правки нескольких ключей и перезагрузки. "
                       "Не рекомендуется.",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/Отключить VSync.reg": {
        "title": "Игры: отключить VSync через Direct3D",
        "description": "FlipNoVsync=1 для Direct3D и WOW6432Node. Современные игры (DXGI/D3D12) значение игнорируют, "
                       "зато возможны разрывы и проблемы композиции.",
        "risk": "caution",
    },
    "Реестр/Отключить гибернация.reg": {
        "title": "Система: отключить гибернацию",
        "description": "HibernateEnabled=0, освобождает hiberfil.sys. Встроено в «Реестр → Система». "
                       "Отключает и быстрый запуск.",
        "risk": "safe",
    },
    "Реестр/Отключить оптимизацию во весь экран.reg": {
        "title": "Игры: отключить fullscreen optimizations",
        "description": "GameConfigStore и политика GameDVR. Встроено в «Реестр → Игры».",
        "risk": "caution",
    },

    "Реестр/ВИДЮХИ/AMD/AMD Tweak Melody.reg": {
        "title": "AMD: мелочи драйвера (~30 значений)",
        "description": "Массовая правка недокументированных значений драйвера AMD. Может дать чёрный экран или артефакты. "
                       "Безопасная альтернатива — твик «AMD: отключить ULPS».",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/AMD/Disable Some Power Savings.reg": {
        "title": "AMD: ULPS off + отключение термотроттлинга",
        "description": "EnableUlps=0 (полезно) и PP_ThermalAutoThrottlingEnable=0 (перегрев и провалы частот). "
                       "В приложении оставлен только безопасный ULPS.",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/AMD/Pre Rendered Frame.reg": {
        "title": "AMD: pre-rendered frames",
        "description": "Правит UMD\\Main3D\\FlipQueueSize. Требует ручного выбора номера GPU-ключа (0000/0001), "
                       "формат значения зависит от версии драйвера.",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/AMD/Tweak Some Radeon Software Settings.reg": {
        "title": "AMD: тесселяция и TFQ",
        "description": "Снижает качество картинки ради FPS, привязано к ключу \\0000. Эффект зависит от игры.",
        "risk": "danger",
        "restart": True,
    },

    "Реестр/ВИДЮХИ/NVIDIA/1 Батники Nvidia/Advanced Hidden Nvidia Gpu Tweaks.bat": {
        "title": "NVIDIA: ~45 скрытых tweaks питания",
        "description": "Массовая запись недокументированных значений Control\\Power (LatencyTolerance*, D3Transition*). "
                       "Может ухудшить автономность и стабильность, откат только бэкапом.",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/NVIDIA/1 Батники Nvidia/Disable Scaling.bat": {
        "title": "NVIDIA: Scaling=1 во всех подклюхах",
        "description": "Правит все GraphicsDrivers\\Configuration подряд. Эффект недоказан, затрагивает чужие профили.",
        "risk": "caution",
    },
    "Реестр/ВИДЮХИ/NVIDIA/1 Батники Nvidia/Force P0-State.bat": {
        "title": "NVIDIA: принудительный P0-стейт",
        "description": "DisableDynamicPstate=1 для найденной карты. Постоянная максимальная частота: нагрев, шум, "
                       "на ноутбуках — троттлинг.",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/NVIDIA/1 Батники Nvidia/Remove ECC.bat": {
        "title": "NVIDIA: отключить ECC",
        "description": "nvidia-smi -e 0 из C:\\Program Files\\NVIDIA Corporation\\NVSMI — в новых драйверах пути нет. "
                       "ECC есть только у профессиональных карт.",
        "risk": "danger",
    },
    "Реестр/ВИДЮХИ/NVIDIA/1 Батники Nvidia/Unrestricted Clock Policy.bat": {
        "title": "NVIDIA: снять ограничение политики частот",
        "description": "nvidia-smi -acp 0 с захардкоженным путём. На потребительских картах не работает.",
        "risk": "danger",
    },
    "Реестр/ВИДЮХИ/NVIDIA/1 Батники Nvidia/Отключение Полноэкранной Оптимизации.bat": {
        "title": "NVIDIA: FSE off + __COMPAT_LAYER",
        "description": "GameDVR/FSE плюс глобальная переменная __COMPAT_LAYER=DISABLEDXMAXIMIZEDWINDOWEDMODE. "
                       "Глобальная переменная влияет на все приложения — в приложении не используется.",
        "risk": "caution",
    },

    "Реестр/ВИДЮХИ/NVIDIA/Boost FPS .reg": {
        "title": "NVIDIA: SFIO Priority + GameMode-блобы",
        "description": "SFIO Priority=High (встроено) и два больших hex-блоба Win32_*, привязанных к конкретной сборке "
                       "Windows. Блобы не переносились в твики.",
        "risk": "caution",
    },
    "Реестр/ВИДЮХИ/NVIDIA/DisableWriteCombining.reg": {
        "title": "NVIDIA: DisableWriteCombining=0",
        "description": "Имя противоречит значению: 0 = write combining включён, это дефолт. Файл ничего не меняет.",
        "risk": "safe",
    },
    "Реестр/ВИДЮХИ/NVIDIA/GameBar, GameDVR.reg": {
        "title": "NVIDIA: GameBar и GameDVR",
        "description": "Отключает Xbox Game Bar и запись. Встроено в «Реестр → Игры».",
        "risk": "caution",
    },
    "Реестр/ВИДЮХИ/NVIDIA/P-state 0.reg": {
        "title": "NVIDIA: P-state 0 (битый путь)",
        "description": "Путь Class\\*\\0000 — звёздочка литеральная, reg.exe создаёт ключ с именем «*». "
                       "Реальные GPU-ключи не меняются. Плюс принудительный P0 = нагрев.",
        "risk": "danger",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/NVIDIA/Rm Gps Ps Enable Per  Cpu Core Dpc.reg": {
        "title": "NVIDIA: DPC по каждому ядру (дубль)",
        "description": "RmGpsPsEnablePerCpuCoreDpc=1. Встроено в «Видеокарту» одним твиком.",
        "risk": "caution",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/NVIDIA/Оптимизация драйвера NVIDIA.reg": {
        "title": "NVIDIA: EnableRID61684",
        "description": "Недокументированный флаг внутренней ревизии драйвера (nvlddmkm\\FTS). Эффект неизвестен.",
        "risk": "caution",
        "restart": True,
    },
    "Реестр/ВИДЮХИ/NVIDIA/Приоритет csrss.reg": {
        "title": "NVIDIA: «приоритет csrss» (D3D12_ENABLE_*)",
        "description": "14 значений в HKLM\\SOFTWARE\\Microsoft\\DirectX, включая UNSAFE_COMMAND_BUFFER_REUSE. "
                       "Рантайм D3D их не читает, а unsafe-флаг провоцирует краши.",
        "risk": "danger",
    },
    "Реестр/ВИДЮХИ/NVIDIA/Уменьшение задержек для nvidia.reg": {
        "title": "NVIDIA: DpiMapIommuContiguous",
        "description": "GraphicsDrivers\\DpiMapIommuContiguous=1. Недокументировано; на системах без IOMMU для GPU — no-op.",
        "risk": "caution",
        "restart": True,
    },

    "Реестр/основное/Buttons.reg": {
        "title": "Ввод: HardwareButtonsAsVKeys=0",
        "description": "Недокументированный ключ SYSTEM\\Input\\Buttons. Влияние на систему неизвестно.",
        "risk": "caution",
    },
    "Реестр/основное/KeyboardDataQueueSize.reg": {
        "title": "Клавиатура: очередь и приоритет драйвера",
        "description": "kbdclass: ThreadPriority=31 (realtime для драйвера клавиатуры), размер очереди, MaximumPortsServiced. "
                       "Может подвесить ввод. Не рекомендуется.",
        "risk": "danger",
        "restart": True,
    },

    "самое лучше энергопитание для игр/Optimize Power Scheme.cmd": {
        "title": "Схема питания «Optimized» (~40 настроек)",
        "description": "Создаёт копию схемы через powercfg /duplicatescheme и задаёт параметры AC/DC. "
                       "Исходная схема остаётся в списке — вернуться можно в «Электропитании».",
        "risk": "caution",
        "undo": "powercfg /setactive SCHEME_BALANCED",
        "undo_label": "Вернуть схему «Сбалансированная»",
    },
}

DEFAULT_META = {
    "title": "",
    "description": "Файл из исходной папки «оптимизация». Запускается вручную, вывод пишется в лог.",
    "risk": "caution",
    "restart": False,
    "undo": "",
    "undo_label": "",
}


def script_meta(relpath: str) -> dict:
    """Мета для относительного пути вида 'материалы/Реестр/Отключить UAC.reg'."""
    key = relpath.replace("\\", "/")
    if key.startswith(_BASE):
        key = key[len(_BASE):]
    meta = dict(DEFAULT_META)
    meta.update(SCRIPTS.get(key, {}))
    if not meta["title"]:
        meta["title"] = key.rsplit("/", 1)[-1]
    meta.setdefault("restart", False)
    return meta
