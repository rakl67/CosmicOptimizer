"""Curated, reversible Windows and Microsoft diagnostic-data policies."""
from __future__ import annotations

import json
import os
import platform
import winreg
from pathlib import Path

from . import admin, config, powershell


_HKLM = winreg.HKEY_LOCAL_MACHINE
_HKCU = winreg.HKEY_CURRENT_USER
_TYPE_NAMES = {
    winreg.REG_SZ: "REG_SZ",
    winreg.REG_DWORD: "REG_DWORD",
    winreg.REG_QWORD: "REG_QWORD",
    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_BINARY: "REG_BINARY",
    winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
}
_TYPES = {
    "REG_SZ": winreg.REG_SZ,
    "REG_DWORD": winreg.REG_DWORD,
    "REG_QWORD": winreg.REG_QWORD,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
    "REG_BINARY": winreg.REG_BINARY,
    "REG_MULTI_SZ": winreg.REG_MULTI_SZ,
}
_STATE_FILE = config.DATA_DIR / "telemetry-baseline.json"

_GROUPS = [
    {"id": "windows", "name": "Windows и компьютер"},
    {"id": "permissions", "name": "Приложения и разрешения Windows"},
    {"id": "microsoft", "name": "Приложения Microsoft"},
    {"id": "browsers", "name": "Другие браузеры"},
]


def _task_control(control_id: str, name: str, description: str, task_path: str) -> dict:
    return {
        "id": control_id,
        "group": "windows",
        "kind": "task",
        "task_path": task_path,
        "name": name,
        "description": description,
        "hive": "HKLM",
        "key": r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache",
        "value": control_id,
        "target": "disabled",
        "min_build": 10240,
    }


def _app_privacy_control(control_id: str, name: str, description: str, value_name: str) -> dict:
    return {
        "id": control_id,
        "group": "permissions",
        "name": name,
        "description": description,
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy",
        "value": value_name,
        "target": 2,
        "min_build": 14393,
    }

_CONTROLS = [
    {
        "id": "diagnostic_data",
        "group": "windows",
        "name": "Диагностические данные Windows",
        "description": "Оставляет минимальный уровень диагностики: Security на Enterprise/Education, Required на остальных редакциях. Обязательные данные безопасности на обычных редакциях Windows полностью не отключаются.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "value": "AllowTelemetry",
        "target": "diagnostic",
        "min_build": 10240,
    },
    {
        "id": "advertising_id",
        "group": "windows",
        "name": "Рекламный идентификатор Windows",
        "description": "Запрещает приложениям Windows использовать рекламный ID для персонализации между приложениями.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo",
        "value": "DisabledByGroupPolicy",
        "target": 1,
        "min_build": 14393,
    },
    {
        "id": "tailored_experiences",
        "group": "windows",
        "name": "Персональные советы и предложения",
        "description": "Не использует диагностические данные для персонализации советов, экрана блокировки и рекомендаций Windows. Сами рекомендации могут остаться, но станут менее персональными.",
        "hive": "HKCU",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
        "value": "DisableTailoredExperiencesWithDiagnosticData",
        "target": 1,
        "min_build": 15063,
    },
    {
        "id": "feedback_notifications",
        "group": "windows",
        "name": "Запросы отзывов Windows",
        "description": "Отключает всплывающие вопросы Microsoft с просьбой оставить отзыв. Не отключает отчёты об ошибках.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "value": "DoNotShowFeedbackNotifications",
        "target": 1,
        "min_build": 14393,
    },
    {
        "id": "diagnostic_logs",
        "group": "windows",
        "name": "Дополнительные диагностические логи",
        "description": "В Windows 11 запрещает сбор дополнительных диагностических логов. Это ограничивает данные для поиска причин редких сбоев.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "value": "LimitDiagnosticLogCollection",
        "target": 1,
        "min_build": 22000,
    },
    {
        "id": "diagnostic_dumps",
        "group": "windows",
        "name": "Полные дампы ошибок",
        "description": "В Windows 11 ограничивает отправку дампов небольшими диагностическими дампами. Отчёты об ошибках не отключаются полностью.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "value": "LimitDumpCollection",
        "target": 1,
        "min_build": 22000,
    },
    {
        "id": "typing_collection",
        "group": "windows",
        "name": "Сбор данных о наборе текста",
        "description": "Ограничивает отправку статистики набора текста для улучшения распознавания. Windows не будет обучать распознавание на ваших данных.",
        "hive": "HKCU",
        "key": r"Software\Microsoft\InputPersonalization",
        "value": "RestrictImplicitTextCollection",
        "target": 1,
        "min_build": 10240,
    },
    {
        "id": "inking_collection",
        "group": "windows",
        "name": "Сбор данных о рукописном вводе",
        "description": "Ограничивает отправку данных рукописного ввода для улучшения распознавания.",
        "hive": "HKCU",
        "key": r"Software\Microsoft\InputPersonalization",
        "value": "RestrictImplicitInkCollection",
        "target": 1,
        "min_build": 10240,
    },
    {
        "id": "online_speech",
        "group": "windows",
        "name": "Облачное распознавание речи",
        "description": "Отключает онлайн-распознавание речи Microsoft. Облачная диктовка и функции приложений, использующие речь Microsoft, перестанут работать. Windows поддерживает эту политику на Pro, Enterprise и Education.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\InputPersonalization",
        "value": "AllowInputPersonalization",
        "target": 0,
        "min_build": 10240,
        "editions": ("pro", "enterprise", "education", "iot"),
    },
    {
        "id": "error_reporting",
        "group": "windows",
        "name": "Отправка отчётов о сбоях Windows",
        "description": "Запрещает Windows Error Reporting отправлять сведения о сбоях Microsoft. Решения проблем в разделе «Безопасность и обслуживание» также станут недоступны. Поддерживается на Pro, Enterprise и Education.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting",
        "value": "Disabled",
        "target": 1,
        "min_build": 15063,
        "editions": ("pro", "enterprise", "education", "iot"),
    },
    {
        "id": "ceip",
        "group": "windows",
        "name": "Программа улучшения Windows (CEIP)",
        "description": "Отключает участие в Customer Experience Improvement Program: Microsoft перестаёт получать статистику использования Windows и часть обезличенной информации о работе системы.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\SQMClient\Windows",
        "value": "CEIPEnable",
        "target": 0,
        "min_build": 19041,
    },
    {
        "id": "application_impact_telemetry",
        "group": "windows",
        "name": "Телеметрия влияния приложений",
        "description": "Отключает сбор данных Application Impact Telemetry о запусках, совместимости и влиянии приложений на систему. Для полного применения новых запусков может потребоваться перезагрузка.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\AppCompat",
        "value": "AITEnable",
        "target": 0,
        "min_build": 19041,
    },
    {
        "id": "application_inventory",
        "group": "windows",
        "name": "Инвентаризация программ и драйверов",
        "description": "Отключает Inventory Collector, который перечисляет установленные программы, устройства и драйверы и отправляет сведения Microsoft для анализа совместимости.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\AppCompat",
        "value": "DisableInventory",
        "target": 1,
        "min_build": 19041,
    },
    {
        "id": "activity_feed",
        "group": "windows",
        "name": "Журнал истории действий",
        "description": "Отключает локальную историю действий Windows. Приложения и функции, которые зависят от Activity History, перестанут получать эту историю.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\System",
        "value": "EnableActivityFeed",
        "target": 0,
        "min_build": 10240,
    },
    {
        "id": "publish_activities",
        "group": "windows",
        "name": "Публикация действий",
        "description": "Запрещает приложениям публиковать действия в системный журнал активности.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\System",
        "value": "PublishUserActivities",
        "target": 0,
        "min_build": 10240,
    },
    {
        "id": "upload_activities",
        "group": "windows",
        "name": "Отправка истории действий в Microsoft",
        "description": "Запрещает отправку истории действий в облачную учётную запись Microsoft и синхронизацию между устройствами.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\System",
        "value": "UploadUserActivities",
        "target": 0,
        "min_build": 10240,
    },
    {
        "id": "search_web_suggestions",
        "group": "windows",
        "name": "Веб-подсказки поиска Windows",
        "description": "Отключает подсказки Bing в поиске меню «Пуск» и проводника. Локальный поиск файлов, программ и параметров продолжит работать.",
        "hive": "HKCU",
        "key": r"Software\Policies\Microsoft\Windows\Explorer",
        "value": "DisableSearchBoxSuggestions",
        "target": 1,
        "min_build": 10240,
    },
    {
        "id": "local_advertising_id",
        "group": "windows",
        "name": "Локальный рекламный профиль",
        "description": "Отключает локальный рекламный идентификатор текущего пользователя. Дополняет системную политику рекламного ID и сохраняется для каждого профиля отдельно.",
        "hive": "HKCU",
        "key": r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
        "value": "Enabled",
        "target": 0,
        "min_build": 10240,
    },
    {
        "id": "diagtrack_service",
        "group": "windows",
        "kind": "service",
        "service": "DiagTrack",
        "name": "Служба телеметрии DiagTrack",
        "description": "Останавливает и отключает автозапуск Connected User Experiences and Telemetry. Служба связана с диагностикой, Feedback Hub и частью сценариев устранения неполадок. Приложение сохраняет исходный тип запуска и состояние службы.",
        "hive": "HKLM",
        "key": r"SYSTEM\CurrentControlSet\Services\DiagTrack",
        "value": "Start",
        "target": 4,
        "min_build": 10240,
    },
    {
        "id": "office_telemetry",
        "group": "microsoft",
        "requires_app": "office",
        "name": "Диагностика Microsoft Office",
        "description": "Устанавливает уровень диагностических данных Microsoft 365 Apps и Office в «Neither»: обязательные и необязательные диагностические данные клиентских приложений Office не отправляются.",
        "hive": "HKCU",
        "key": r"Software\Policies\Microsoft\office\common\clienttelemetry",
        "value": "SendTelemetry",
        "target": 3,
        "min_build": 10240,
    },
    {
        "id": "edge_diagnostic_data",
        "group": "microsoft",
        "requires_app": "edge",
        "name": "Диагностика Microsoft Edge",
        "description": "Оставляет только обязательные диагностические данные Edge, необходимые для безопасности и обновлений, и отключает необязательные данные об использовании и посещённых сайтах.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Edge",
        "value": "DiagnosticData",
        "target": 1,
        "min_build": 22631,
    },
    {
        "id": "edge_personalization",
        "group": "microsoft",
        "requires_app": "edge",
        "name": "Персонализация Microsoft Edge",
        "description": "Запрещает использовать историю просмотров, избранное, коллекции и данные использования Edge для персонализации рекламы, поиска, новостей и других сервисов Microsoft.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Edge",
        "value": "PersonalizationReportingEnabled",
        "target": 0,
        "min_build": 10240,
    },
    {
        "id": "chrome_metrics",
        "group": "browsers",
        "requires_app": "chrome",
        "name": "Диагностика Google Chrome",
        "description": "Отключает отправку в Google анонимных данных об использовании и стабильности браузера через корпоративную политику Chrome.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Google\Chrome",
        "value": "MetricsReportingEnabled",
        "target": 0,
        "min_build": 10240,
    },
    {
        "id": "firefox_telemetry",
        "group": "browsers",
        "requires_app": "firefox",
        "name": "Телеметрия Mozilla Firefox",
        "description": "Отключает отправку телеметрии и отчётов об использовании Firefox в Mozilla через поддерживаемые политики предприятия.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Mozilla\Firefox",
        "value": "DisableTelemetry",
        "target": 1,
        "min_build": 10240,
    },
    {
        "id": "privacy_experience",
        "group": "windows",
        "name": "Экран согласия с параметрами конфиденциальности",
        "description": "Отключает повторное предложение принять рекомендуемые параметры конфиденциальности Windows после обновлений. Не меняет уже выбранные настройки.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\OOBE",
        "value": "DisablePrivacyExperience",
        "target": 1,
        "min_build": 10240,
    },
    {
        "id": "consumer_features",
        "group": "windows",
        "name": "Рекомендованный потребительский контент Windows",
        "description": "Запрещает Windows автоматически предлагать или устанавливать рекламные приложения и контент Microsoft. Не удаляет уже установленные приложения.",
        "hive": "HKLM",
        "key": r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
        "value": "DisableWindowsConsumerFeatures",
        "target": 1,
        "min_build": 10240,
    },
    {
        "id": "dotnet_telemetry",
        "group": "microsoft",
        "name": "Телеметрия .NET CLI",
        "description": "Устанавливает для текущего пользователя DOTNET_CLI_TELEMETRY_OPTOUT=1. Перезапустите Проводник, войдите в Windows заново или откройте новый терминал, чтобы новые процессы .NET CLI не отправляли данные использования Microsoft.",
        "hive": "HKCU",
        "key": r"Environment",
        "value": "DOTNET_CLI_TELEMETRY_OPTOUT",
        "target": "1",
        "value_type": "REG_SZ",
        "min_build": 10240,
    },
    {
        "id": "powershell_telemetry",
        "group": "microsoft",
        "name": "Телеметрия PowerShell",
        "description": "Устанавливает POWERSHELL_TELEMETRY_OPTOUT=1 для текущего пользователя. Перезапустите Проводник, войдите в Windows заново или откройте новый терминал, чтобы новые процессы PowerShell 7 перестали отправлять телеметрию использования.",
        "hive": "HKCU",
        "key": r"Environment",
        "value": "POWERSHELL_TELEMETRY_OPTOUT",
        "target": "1",
        "value_type": "REG_SZ",
        "min_build": 10240,
    },
    _task_control("compatibility_appraiser", "Проверка совместимости приложений", "Отключает задание Microsoft Compatibility Appraiser, собирающее сведения о совместимости системы и приложений для Microsoft.", r"\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser"),
    _task_control("program_data_updater", "Обновление данных совместимости", "Отключает ProgramDataUpdater — фоновую задачу обновления данных о совместимости установленных программ.", r"\Microsoft\Windows\Application Experience\ProgramDataUpdater"),
    _task_control("application_impact_task", "Задача агента телеметрии приложений", "Отключает AITAgent, который собирает данные о запусках и влиянии приложений на систему.", r"\Microsoft\Windows\Application Experience\AitAgent"),
    _task_control("ceip_consolidator", "Задача CEIP", "Отключает задачу Consolidator программы улучшения качества Windows (CEIP).", r"\Microsoft\Windows\Customer Experience Improvement Program\Consolidator"),
    _app_privacy_control("camera_access", "Доступ приложений к камере", "Запрещает приложениям Windows доступ к камере. Видеозвонки, сканеры QR и фото-приложения перестанут использовать камеру.", "LetAppsAccessCamera"),
    _app_privacy_control("microphone_access", "Доступ приложений к микрофону", "Запрещает приложениям Windows доступ к микрофону. Голосовые звонки и запись звука в приложениях перестанут работать.", "LetAppsAccessMicrophone"),
    _app_privacy_control("location_access", "Доступ приложений к местоположению", "Запрещает приложениям Windows получать геопозицию устройства.", "LetAppsAccessLocation"),
    _app_privacy_control("contacts_access", "Доступ приложений к контактам", "Запрещает приложениям Windows получать список контактов.", "LetAppsAccessContacts"),
    _app_privacy_control("calendar_access", "Доступ приложений к календарю", "Запрещает приложениям Windows получать данные календаря.", "LetAppsAccessCalendar"),
    _app_privacy_control("email_access", "Доступ приложений к электронной почте", "Запрещает приложениям Windows получать доступ к почте и метаданным сообщений.", "LetAppsAccessEmail"),
    _app_privacy_control("messaging_access", "Доступ приложений к сообщениям", "Запрещает приложениям Windows читать или отправлять SMS и сообщения.", "LetAppsAccessMessaging"),
    _app_privacy_control("diagnostics_access", "Диагностика приложений", "Запрещает приложениям Windows получать диагностические сведения о других приложениях.", "LetAppsAccessAppDiagnostics"),
    _app_privacy_control("account_info_access", "Доступ приложений к данным учётной записи", "Запрещает приложениям Windows получать имя, изображение и другие сведения учётной записи.", "LetAppsAccessAccountInfo"),
    _app_privacy_control("documents_access", "Доступ приложений к документам", "Запрещает приложениям Windows доступ к библиотеке документов.", "LetAppsAccessDocuments"),
    _app_privacy_control("pictures_access", "Доступ приложений к изображениям", "Запрещает приложениям Windows доступ к библиотеке изображений.", "LetAppsAccessPictures"),
    _app_privacy_control("videos_access", "Доступ приложений к видео", "Запрещает приложениям Windows доступ к библиотеке видео.", "LetAppsAccessVideos"),
    _app_privacy_control("filesystem_access", "Доступ приложений к файловой системе", "Запрещает приложениям Windows широкий доступ к файловой системе. Некоторые приложения могут потерять доступ к выбранным файлам.", "LetAppsAccessFileSystem"),
    _app_privacy_control("radios_access", "Управление радиомодулями", "Запрещает приложениям Windows управлять Bluetooth, Wi‑Fi и другими радиомодулями.", "LetAppsAccessRadios"),
    _app_privacy_control("other_devices_access", "Доступ к другим устройствам", "Запрещает приложениям Windows обмениваться данными с сопряжёнными устройствами.", "LetAppsAccessTrustedDevices"),
]
_BY_ID = {item["id"]: item for item in _CONTROLS}
_APP_LABELS = {
    "office": "Microsoft Office",
    "edge": "Microsoft Edge",
    "chrome": "Google Chrome",
    "firefox": "Mozilla Firefox",
}
_APP_EXECUTABLES = {
    "office": ("WINWORD.EXE", "EXCEL.EXE", "POWERPNT.EXE"),
    "edge": ("msedge.exe",),
    "chrome": ("chrome.exe",),
    "firefox": ("firefox.exe",),
}
_APP_PATHS = {
    "office": (
        ("ProgramFiles", "Microsoft Office", "root", "Office16", "WINWORD.EXE"),
        ("ProgramFiles(x86)", "Microsoft Office", "root", "Office16", "WINWORD.EXE"),
    ),
    "edge": (
        ("ProgramFiles(x86)", "Microsoft", "Edge", "Application", "msedge.exe"),
        ("ProgramFiles", "Microsoft", "Edge", "Application", "msedge.exe"),
    ),
    "chrome": (
        ("ProgramFiles", "Google", "Chrome", "Application", "chrome.exe"),
        ("ProgramFiles(x86)", "Google", "Chrome", "Application", "chrome.exe"),
        ("LOCALAPPDATA", "Google", "Chrome", "Application", "chrome.exe"),
    ),
    "firefox": (
        ("ProgramFiles", "Mozilla Firefox", "firefox.exe"),
        ("ProgramFiles(x86)", "Mozilla Firefox", "firefox.exe"),
    ),
}


def _windows_build() -> int:
    try:
        with winreg.OpenKey(_HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            return int(winreg.QueryValueEx(key, "CurrentBuild")[0])
    except (OSError, TypeError, ValueError):
        return 0


def _edition() -> str:
    try:
        with winreg.OpenKey(_HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            return str(winreg.QueryValueEx(key, "ProductName")[0])
    except OSError:
        return platform.platform()


def _security_level_supported(edition: str) -> bool:
    name = edition.casefold()
    return any(part in name for part in ("enterprise", "education", "iot"))


def _target(item: dict, edition: str):
    if item["target"] == "diagnostic":
        return 0 if _security_level_supported(edition) else 1
    return item["target"]


def _registry_key_exists(hive: int, key_path: str) -> bool:
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ):
            return True
    except OSError:
        return False


def _file_exists_from_environment(parts: tuple[str, ...]) -> bool:
    root = os.environ.get(parts[0])
    if not root:
        return False
    try:
        return Path(root).joinpath(*parts[1:]).is_file()
    except OSError:
        return False


def _app_installed(app_id: str) -> bool:
    if any(_file_exists_from_environment(parts) for parts in _APP_PATHS.get(app_id, ())):
        return True
    for executable in _APP_EXECUTABLES.get(app_id, ()):
        app_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
        if _registry_key_exists(_HKCU, app_path) or _registry_key_exists(_HKLM, app_path):
            return True
    if app_id == "office" and _registry_key_exists(_HKLM, r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration"):
        return True
    return False


def _requires_admin(item: dict) -> bool:
    return item["hive"] == "HKLM"


def _availability(item: dict, build: int, edition: str) -> tuple[bool, str]:
    if build < item["min_build"]:
        return False, "Требуется Windows " + ("11" if item["min_build"] >= 22000 else "10")
    if item.get("editions") and not any(part in edition.casefold() for part in item["editions"]):
        return False, "Требуется Windows Pro, Enterprise или Education"
    app_id = item.get("requires_app")
    if app_id and not _app_installed(app_id):
        return False, f"{_APP_LABELS.get(app_id, 'Приложение')} не обнаружен"
    if item.get("kind") == "service" and not _registry_key_exists(_HKLM, item["key"]):
        return False, "Служба не найдена в этой версии Windows"
    if item.get("kind") == "task":
        task = _task_state(item["task_path"])
        if task == "missing":
            return False, "Задание не найдено в этой версии Windows"
        if task == "error":
            return False, "Не удалось прочитать состояние задания планировщика"
    return True, ""


def _supported(item: dict, build: int, edition: str) -> bool:
    return _availability(item, build, edition)[0]


def _read(item: dict) -> dict:
    if item.get("kind") == "task":
        state = _task_state(item["task_path"])
        if state == "missing":
            return {"exists": False, "value": None, "type": "TASK"}
        if state == "error":
            return {"exists": False, "value": None, "type": "TASK", "error": "Не удалось прочитать состояние задания планировщика"}
        return {"exists": True, "value": state, "type": "TASK"}
    hive = _HKLM if item["hive"] == "HKLM" else _HKCU
    try:
        with winreg.OpenKey(hive, item["key"], 0, winreg.KEY_READ) as key:
            value, value_type = winreg.QueryValueEx(key, item["value"])
            return {"exists": True, "value": value, "type": _TYPE_NAMES.get(value_type, "REG_DWORD")}
    except FileNotFoundError:
        return {"exists": False, "value": None, "type": "REG_DWORD"}
    except OSError as exc:
        return {"exists": False, "value": None, "type": "REG_DWORD", "error": f"Не удалось прочитать параметр реестра: {exc}"}


def _read_managed_value(item: dict) -> dict:
    current = _read(item)
    if current.get("error"):
        raise RuntimeError(f"{item['name']}: {current['error']}")
    expected_type = item.get("value_type", "REG_DWORD")
    if item.get("kind") == "task":
        return current
    if current["exists"] and (current["type"] != expected_type or (expected_type == "REG_DWORD" and not isinstance(current["value"], int))):
        raise RuntimeError(f"{item['name']}: найден нестандартный тип реестра; значение не изменено")
    if item.get("kind") == "service":
        current["running"] = _service_running(item["service"])
    return current


def _write(item: dict, value, value_type: str = "REG_DWORD") -> None:
    if item.get("kind") == "task":
        _set_task_state(item["task_path"], value)
        return
    hive = _HKLM if item["hive"] == "HKLM" else _HKCU
    try:
        with winreg.CreateKeyEx(hive, item["key"], 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, item["value"], 0, _TYPES.get(value_type, winreg.REG_DWORD), value)
    except PermissionError as exc:
        raise RuntimeError("Нужны права администратора для системной политики") from exc


def _delete(item: dict) -> None:
    if item.get("kind") == "task":
        return
    hive = _HKLM if item["hive"] == "HKLM" else _HKCU
    try:
        with winreg.OpenKey(hive, item["key"], 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, item["value"])
    except FileNotFoundError:
        return
    except PermissionError as exc:
        raise RuntimeError("Нужны права администратора для системной политики") from exc


def _load_state() -> dict:
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"originals": {}}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Не удалось прочитать снимок телеметрии: {exc}") from exc
    originals = data.get("originals", {}) if isinstance(data, dict) else {}
    if not isinstance(originals, dict):
        raise RuntimeError("Снимок телеметрии повреждён; текущие параметры Windows не менялись")
    return {"originals": originals}


def _save_state(data: dict) -> None:
    config.ensure_dirs()
    temp = _STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(_STATE_FILE)


def _service_running(service_name: str) -> bool:
    try:
        status = powershell.run(
            f"(Get-Service -Name '{service_name}' -ErrorAction Stop).Status.ToString()",
            timeout=30,
        )
        return status.strip().casefold() == "running"
    except Exception:  # noqa: BLE001 - status is informative; the registry policy remains usable
        return False


def _task_parts(task_path: str) -> tuple[str, str]:
    parent, _, name = task_path.rpartition("\\")
    return parent + "\\", name


def _task_state(task_path: str) -> str:
    task_parent, task_name = _task_parts(task_path)
    try:
        state = powershell.run(
            f"$task = Get-ScheduledTask -TaskPath '{task_parent}' -TaskName '{task_name}' -ErrorAction SilentlyContinue; "
            "if ($null -eq $task) { 'missing' } elseif ($task.State -eq 'Disabled') { 'disabled' } else { 'enabled' }",
            timeout=30,
        ).strip().casefold()
        return state if state in {"missing", "disabled", "enabled"} else "error"
    except Exception:  # noqa: BLE001 - status is informative until an action is requested
        return "error"


def _set_task_state(task_path: str, state: str) -> None:
    if state not in {"enabled", "disabled"}:
        raise RuntimeError("Неизвестное состояние задания планировщика")
    task_parent, task_name = _task_parts(task_path)
    command = "Disable-ScheduledTask" if state == "disabled" else "Enable-ScheduledTask"
    try:
        powershell.run(
            f"$task = Get-ScheduledTask -TaskPath '{task_parent}' -TaskName '{task_name}' -ErrorAction Stop; "
            f"{command} -InputObject $task -ErrorAction Stop | Out-Null",
            timeout=45,
        )
    except Exception as exc:  # noqa: BLE001 - surface the OS error to the user
        raise RuntimeError(f"Не удалось изменить состояние задания: {exc}") from exc


def _stop_service(item: dict) -> None:
    service_name = item["service"]
    try:
        powershell.run(
            f"$s=Get-Service -Name '{service_name}' -ErrorAction Stop; "
            f"if ($s.Status -ne 'Stopped') {{ Stop-Service -Name '{service_name}' -Force -ErrorAction Stop }}",
            timeout=45,
        )
    except Exception as exc:  # noqa: BLE001 - report an actionable service error
        raise RuntimeError(f"Не удалось остановить службу {service_name}: {exc}") from exc


def _start_service(item: dict) -> None:
    service_name = item["service"]
    try:
        powershell.run(
            f"Start-Service -Name '{service_name}' -ErrorAction Stop",
            timeout=45,
        )
    except Exception as exc:  # noqa: BLE001 - policy has already been restored
        raise RuntimeError(f"Тип запуска восстановлен, но службу {service_name} не удалось запустить: {exc}") from exc


def _is_minimized(item: dict, current: dict, edition: str) -> bool:
    if not current["exists"]:
        return False
    value = current["value"]
    if item.get("kind") == "task":
        return value == "disabled"
    if item["id"] == "diagnostic_data" and not _security_level_supported(edition):
        # Microsoft treats Security/0 as Required/1 on unsupported editions.
        return value in (0, 1)
    return value == _target(item, edition)


def _state_label(item: dict, current: dict, edition: str) -> str:
    if current.get("error"):
        return current["error"]
    if not current["exists"]:
        return "По умолчанию Windows"
    value = current["value"]
    if item.get("kind") == "task":
        return "Задание отключено" if value == "disabled" else "Задание включено"
    if item["id"] == "diagnostic_data":
        labels = {0: "Security — минимум", 1: "Required — обязательные данные", 2: "Enhanced — расширенные данные", 3: "Full — все диагностические данные"}
        label = labels.get(value, f"Неизвестное значение ({value})")
        if value == 0 and not _security_level_supported(edition):
            return "Минимум Windows (на этой редакции действует как Required)"
        return label
    if item.get("kind") == "service":
        labels = {0: "Загрузочный драйвер", 1: "Системный драйвер", 2: "Автоматически", 3: "Вручную", 4: "Отключена"}
        label = labels.get(value, f"Неизвестный тип запуска ({value})")
        if value == 4:
            return "Служба остановлена, автозапуск отключён" if not current.get("running") else "Автозапуск отключён, служба остановится после перезагрузки"
        return label + (" · работает" if current.get("running") else " · остановлена")
    return "Ограничено политикой" if _is_minimized(item, current, edition) else "Политика не ограничивает сбор"


def status() -> dict:
    build = _windows_build()
    edition = _edition()
    state = _load_state()
    originals = state["originals"]
    controls = []
    for item in _CONTROLS:
        current = _read(item)
        if item.get("kind") == "service":
            current["running"] = _service_running(item["service"])
        available, reason = _availability(item, build, edition)
        if current.get("error"):
            available, reason = False, current["error"]
        controls.append({
            "id": item["id"],
            "group": item["group"],
            "name": item["name"],
            "description": item["description"],
            "available": available,
            "unavailable_reason": reason,
            "requires_admin": _requires_admin(item),
            "minimized": available and _is_minimized(item, current, edition),
            "managed": item["id"] in originals,
            "state_label": _state_label(item, current, edition),
        })
    return {
        "edition": edition,
        "build": build,
        "admin": admin.is_admin(),
        "security_level_supported": _security_level_supported(edition),
        "groups": _GROUPS,
        "controls": controls,
        "managed_count": len(originals),
        "minimized_count": sum(1 for item in controls if item["available"] and item["minimized"]),
    }


def apply_control(control_id: str) -> dict:
    item = _BY_ID.get(control_id)
    if not item:
        raise ValueError("Неизвестный параметр телеметрии")
    if _requires_admin(item) and not admin.is_admin():
        raise RuntimeError("Запустите приложение от администратора для системных политик")
    build = _windows_build()
    available, reason = _availability(item, build, _edition())
    if not available:
        raise RuntimeError(reason)
    data = _load_state()
    current = _read_managed_value(item)
    if control_id not in data["originals"]:
        data["originals"][control_id] = current
        _save_state(data)
    desired = _target(item, _edition())
    if not current["exists"] or current["value"] != desired:
        _write(item, desired, item.get("value_type", "REG_DWORD"))
    if item.get("kind") == "service" and current.get("running"):
        _stop_service(item)
    config.logger.info("Ограничен сбор телеметрии: %s", item["name"])
    return {"id": control_id, "state": status(), "message": f"«{item['name']}»: ограничение активировано"}


def restore_control(control_id: str) -> dict:
    item = _BY_ID.get(control_id)
    if not item:
        raise ValueError("Неизвестный параметр телеметрии")
    if _requires_admin(item) and not admin.is_admin():
        raise RuntimeError("Запустите приложение от администратора для системных политик")
    data = _load_state()
    original = data["originals"].get(control_id)
    if not isinstance(original, dict):
        raise RuntimeError("Приложение не меняло этот параметр — безопасный откат недоступен")
    if original.get("exists"):
        _write(item, original.get("value"), original.get("type", "REG_DWORD"))
    else:
        _delete(item)
    if item.get("kind") == "service" and original.get("running"):
        _start_service(item)
    del data["originals"][control_id]
    _save_state(data)
    config.logger.info("Восстановлен параметр телеметрии: %s", item["name"])
    return {"id": control_id, "state": status(), "message": f"«{item['name']}»: исходное состояние восстановлено"}


def apply_profile() -> dict:
    data = _load_state()
    build = _windows_build()
    edition = _edition()
    results = []
    for item in _CONTROLS:
        available, reason = _availability(item, build, edition)
        if not available:
            results.append({"id": item["id"], "ok": False, "error": reason})
            continue
        if _requires_admin(item) and not admin.is_admin():
            results.append({"id": item["id"], "ok": False, "error": "Нужны права администратора"})
            continue
        current = _read_managed_value(item)
        if item["id"] not in data["originals"]:
            data["originals"][item["id"]] = current
    _save_state(data)
    for item in _CONTROLS:
        available, _ = _availability(item, build, edition)
        if not available or (_requires_admin(item) and not admin.is_admin()):
            continue
        try:
            current = _read_managed_value(item)
            desired = _target(item, edition)
            if not current["exists"] or current["value"] != desired:
                _write(item, desired, item.get("value_type", "REG_DWORD"))
            if item.get("kind") == "service" and current.get("running"):
                _stop_service(item)
            results.append({"id": item["id"], "ok": True})
        except Exception as exc:  # noqa: BLE001 - apply other safe settings if one policy fails
            results.append({"id": item["id"], "ok": False, "error": str(exc)})
    config.logger.info("Активирован профиль ограничения телеметрии")
    return {
        "results": results,
        "state": status(),
        "applied": sum(1 for result in results if result["ok"]),
        "total": sum(1 for item in _CONTROLS if _supported(item, build, edition)),
    }


def restore_profile() -> dict:
    data = _load_state()
    results = []
    for control_id in list(data["originals"]):
        try:
            result = restore_control(control_id)
            results.append({"id": control_id, "ok": True, "message": result["message"]})
        except Exception as exc:  # noqa: BLE001 - keep restoring other entries
            results.append({"id": control_id, "ok": False, "error": str(exc)})
    return {
        "results": results,
        "state": status(),
        "restored": sum(1 for result in results if result["ok"]),
        "total": len(results),
    }
