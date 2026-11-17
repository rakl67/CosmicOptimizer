"""Внешние инструменты: прямые загрузки, туториалы, дебафф-скрипт и профили."""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import webbrowser
import winreg
from pathlib import Path

from . import config
from .config import logger

CREATE_NEW_CONSOLE = 0x00000010
DOWNLOAD_DIR = config.DATA_DIR / "downloads"
PROFILES_DIR = config.DATA_DIR / "profiles"
GPU_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
DEBLOAT_COMMAND = '& ([scriptblock]::Create((irm "https://debloat.raphi.re/")))'

TOOLS = [
    {
        "id": "boosterx",
        "group": "games",
        "title": "BoosterX",
        "tagline": "Оптимизация Windows под игры в один клик",
        "description": "Скачивается установщик. Внутри — профили оптимизации Windows, отключение фоновых "
                       "служб и настройка питания. Работает локально после установки.",
        "url": "https://github.com/BoosterX/BoosterX/releases/latest/download/BoosterX.exe",
        "fallback_urls": [
            "https://boosterx.org/download/BoosterX.exe",
            "https://dl.boosterx.org/BoosterX.exe"
        ],
        "action": "download",
        "filename": "BoosterX.exe",
        "steps": [
            "Нажмите «Скачать BoosterX» — файл сохранится в папку загрузок приложения.",
            "Запустите BoosterX.exe и установите программу.",
            "Откройте BoosterX → раздел профилей (Profiles).",
            "Нажмите «Профиль» в этом приложении — откроется папка, куда положить файл профиля.",
            "В BoosterX выберите «Импорт профиля» и укажите файл из этой папки.",
            "Проверьте список изменений, нажмите «Применить» и перезагрузите ПК.",
        ],
        "risk": "caution",
    },
    {
        "id": "boosterx_profile",
        "group": "games",
        "title": "BoosterX — Пак оптимизаций",
        "tagline": "Профиль настроек для BoosterX (BackUp_0.buxz)",
        "description": "Готовый профиль оптимизации Windows для BoosterX. Скачается в папку профилей приложения. "
                       "В BoosterX: Профили → Импорт → выберите этот файл → Применить.",
        "url": "assets/BackUp_0.buxz",
        "action": "download_profile",
        "filename": "BackUp_0.buxz",
        "steps": [
            "Нажмите «Скачать профиль» — файл сохранится в папку профилей приложения.",
            "Откройте BoosterX → раздел Профили (Profiles).",
            "Нажмите «Импорт профиля» и выберите BackUp_0.buxz из папки профилей.",
            "Проверьте список изменений, нажмите «Применить» и перезагрузите ПК.",
        ],
        "risk": "safe",
    },
    {
        "id": "process_lasso",
        "group": "games",
        "title": "Process Lasso",
        "tagline": "Приоритеты процессов и ProBalance",
        "description": "Сторонняя программа для тонкой настройки приоритетов игр. Файл лежит на Яндекс.Диске — "
                       "приложение скачает его напрямую в свою папку загрузок.",
        "url": "https://disk.yandex.ru/d/lUlUVzvyzUzfjg",
        "fallback_urls": [
            "https://bitsum.com/files/processlassosetup.exe"
        ],
        "action": "download",
        "filename": "processlassosetup32.exe",
        "steps": [
            "Нажмите «Скачать Process Lasso» — файл сохранится в папку загрузок приложения.",
            "Установите программу и запустите её от администратора.",
            "Найдите игру (например, cs2.exe) в списке процессов, нажмите правой кнопкой.",
            "Приоритет CPU → «Всегда» → «Высокий».",
            "Приоритет ввода-вывода → «Всегда» → «Высокий».",
            "Приоритет GPU → «Всегда» → «Высокий».",
            "Производительный режим → включить, Эффективный режим → выключить.",
            "«Исключить из ProBalance» → включить, чтобы ProBalance не снижал приоритет игры.",
            "Снимите игру с 0-го ядра: в настройках приоритета выберите «CPU Affinity» → «Всегда» → "
            "снимите галочку с CPU 0 и примените.",
        ],
        "risk": "safe",
    },
    {
        "id": "msi_utility",
        "group": "games",
        "title": "MSI Utility V3",
        "tagline": "Высокий приоритет прерываний видеокарты (MSI mode)",
        "description": "Утилита переводит видеокарту в режим MSI (Message Signaled Interrupts) с высоким "
                       "приоритетом прерываний. Файл лежит на Яндекс.Диске — приложение скачает его напрямую.",
        "url": "https://disk.yandex.ru/d/UqaIX8wpXTYikA",
        "fallback_urls": [
            "https://github.com/Barneyyy/MSI-Utility-V3/releases/download/v3/MSI_util_v3.exe"
        ],
        "action": "download",
        "filename": "MSI_util_v3.exe",
        "steps": [
            "Нажмите «Скачать MSI Utility» — файл сохранится в папку загрузок приложения.",
            "Запустите MSI_util_v3.exe от администратора.",
            "Найдите в списке свою видеокарту и поставьте галочку напротив неё.",
            "В колонке приоритета выберите «High».",
            "Нажмите «Apply» в правом верхнем углу.",
            "Перезагрузите ПК, чтобы прерывания переключились.",
        ],
        "risk": "caution",
    },
    {
        "id": "debloat",
        "group": "system",
        "title": "Debloat Windows (raphi)",
        "tagline": "Базовый пресет очистки системы",
        "description": "Открывает отдельное окно PowerShell и запускает официальный скрипт debloat.raphi.re. "
                       "В окне нужно выбрать базовую настройку («Default» / «Basic») и подтвердить. "
                       "Приложение само ничего не выбирает, чтобы вы видели каждый шаг.",
        "url": "https://debloat.raphi.re/",
        "action": "powershell",
        "filename": "",
        "steps": [
            "Нажмите «Запустить Debloat» — откроется окно PowerShell.",
            "Дождитесь загрузки скрипта и появления меню.",
            "Выберите базовую настройку (обычно пункт «Default» или «Basic»).",
            "Подтвердите применение и дождитесь окончания.",
            "Перезагрузите компьютер.",
            "Если что-то перестало работать — верните систему точкой восстановления.",
        ],
        "risk": "caution",
    },
    {
        "id": "custom_windows",
        "group": "system",
        "title": "Кастомная Windows (AME Wizard + ReviOS)",
        "tagline": "Сборка без потери данных",
        "description": "Официальный способ: AME Wizard накладывает Playbook ReviOS на текущую систему. "
                       "Данные и программы сохраняются, но это серьёзная переделка Windows — только после "
                       "точки восстановления и с отключённым антивирусом.",
        "url": "https://revi.cc",
        "action": "open",
        "filename": "",
        "steps": [
            "Создайте точку восстановления (кнопка есть в разделе «Бэкапы»).",
            "Откройте сайт revi.cc и скачайте AME Wizard и Playbook ReviOS.",
            "Временно отключите Defender и сторонний антивирус.",
            "Запустите AME Wizard, загрузите Playbook и следуйте инструкциям на экране.",
            "После перезагрузки система будет оптимизирована, файлы и программы останутся на месте.",
        ],
        "risk": "danger",
    },
]


def tools_catalog() -> list[dict]:
    return TOOLS


def tool_by_id(tool_id: str) -> dict:
    for tool in TOOLS:
        if tool["id"] == tool_id:
            return tool
    raise ValueError("Неизвестный инструмент")


def _ensure_downloads() -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def _fetch(url: str, target: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": "CosmicOptimizer/1.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as handle:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    handle.write(chunk)
            if not target.exists() or target.stat().st_size < 1024:
                raise RuntimeError("Сервер вернул пустой файл. Попробуйте открыть страницу загрузки вручную")
            return target
        except urllib.error.URLError as e:
            last_error = e
            logger.warning("Попытка %d/3 не удалась: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Не удалось скачать после 3 попыток: {last_error}")


def _yandex_direct(public_url: str) -> str:
    """Публичная ссылка Яндекс.Диска → прямая ссылка на файл (без ключей и регистрации)."""
    api = (
        "https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key="
        + urllib.parse.quote(public_url, safe="")
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(api, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            href = data.get("href")
            if not href:
                raise RuntimeError("Яндекс.Диск не выдал ссылку на файл")
            return href
        except urllib.error.URLError as e:
            last_error = e
            logger.warning("Яндекс.Диск API попытка %d/3 не удалась: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Яндекс.Диск API недоступен после 3 попыток: {last_error}")


def download_tool(tool_id: str) -> dict:
    tool = tool_by_id(tool_id)
    if tool["action"] == "powershell":
        raise RuntimeError("Этот инструмент запускается кнопкой «Запустить Debloat»")
    if tool["action"] == "open":
        webbrowser.open(tool["url"])
        return {"opened": True, "url": tool["url"], "message": "Страница открыта в браузере"}

    if tool["action"] == "download_profile":
        # Копируем встроенный профиль в пользовательскую папку профилей.
        profiles_dir = PROFILES_DIR
        profiles_dir.mkdir(parents=True, exist_ok=True)
        target = profiles_dir / tool["filename"]
        
        # При сборке файл берётся из архива EXE, при разработке — из assets/.
        if config.FROZEN:
            import sys
            src = Path(sys._MEIPASS) / "assets" / tool["filename"]
        else:
            src = config.ROOT_DIR / "assets" / tool["filename"]
        
        if not src.exists():
            raise RuntimeError(f"Файл профиля не найден в сборке: {src}")
        
        if target.exists() and target.stat().st_size == src.stat().st_size:
            os.startfile(str(profiles_dir))  # noqa: S606
            return {"path": str(target), "cached": True, "message": "Профиль уже есть"}
        
        import shutil
        shutil.copy2(src, target)
        logger.info("Профиль скопирован: %s → %s", src, target)
        os.startfile(str(profiles_dir))  # noqa: S606
        return {"path": str(target), "cached": False, "message": f"Профиль готов: {target.name}"}

    folder = _ensure_downloads()
    target = folder / (tool["filename"] or "download.exe")
    if target.exists() and target.stat().st_size > 1024:
        os.startfile(str(folder))  # noqa: S606 - локальная папка
        return {"path": str(target), "cached": True, "message": "Файл уже скачан"}

    urls = [tool["url"]]
    if "fallback_urls" in tool:
        urls.extend(tool["fallback_urls"])

    last_error = None
    for idx, url in enumerate(urls):
        try:
            download_url = url
            if "disk.yandex" in url:
                download_url = _yandex_direct(url)
            logger.info("Скачивание %s → %s (источник %d/%d)", tool_id, target.name, idx + 1, len(urls))
            _fetch(download_url, target)
            logger.info("Скачано: %s (%.1f МБ)", target.name, target.stat().st_size / 1048576)
            os.startfile(str(folder))  # noqa: S606
            return {"path": str(target), "cached": False, "message": f"Скачано: {target.name}"}
        except Exception as e:
            last_error = e
            logger.warning("Источник %d/%d не удался: %s", idx + 1, len(urls), e)

    raise RuntimeError(f"Все источники недоступны: {last_error}")


def open_link(tool_id: str) -> dict:
    tool = tool_by_id(tool_id)
    webbrowser.open(tool["url"])
    return {"url": tool["url"]}


def run_debloat() -> dict:
    """Открывает видимое окно PowerShell со скриптом дебаффа. Пользователь выбирает пресет сам."""
    logger.info("Запуск debloat в отдельном окне PowerShell")
    process = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-NoExit",
            "-Command",
            DEBLOAT_COMMAND,
        ],
        creationflags=CREATE_NEW_CONSOLE,
    )
    return {
        "pid": process.pid,
        "message": "Окно PowerShell открыто. Выберите базовую настройку и подтвердите.",
    }


def profiles_dir() -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def open_profiles() -> dict:
    path = profiles_dir()
    try:
        readme = path / "Как-положить-профиль.txt"
        if not readme.exists():
            readme.write_text(
                "Положите сюда файл профиля BoosterX (.bxprofile или .json).\n"
                "Затем откройте BoosterX → Профили → Импорт и выберите этот файл.\n",
                encoding="utf-8",
            )
    except OSError:
        pass
    os.startfile(str(path))  # noqa: S606
    return {"path": str(path), "files": [p.name for p in path.iterdir() if p.is_file()]}


def gpu_vendor() -> dict:
    """Определяет производителя GPU по описанию драйвера в классе Display."""
    vendors = set()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, GPU_CLASS) as root:
            index = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                if not sub.isdigit():
                    continue
                try:
                    with winreg.OpenKey(root, sub) as key:
                        desc = str(winreg.QueryValueEx(key, "DriverDesc")[0])
                except OSError:
                    continue
                upper = desc.upper()
                if "NVIDIA" in upper:
                    vendors.add("nvidia")
                elif "AMD" in upper or "RADEON" in upper:
                    vendors.add("amd")
                elif "INTEL" in upper:
                    vendors.add("intel")
    except OSError:
        pass
    return {"vendors": sorted(vendors)}
