"""Безопасная очистка мусора: только белый список путей, ничего важного."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import powershell
from . import jobs
from .config import logger, DATA_DIR

CREATE_NO_WINDOW = 0x08000000
OLD_FILE_SECONDS = 30 * 60  # свежие файлы не трогаем: их может держать установщик
CACHE_NAMES = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "DawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "ShaderCache",
    "GrShaderCache",
}
BROWSERS = {
    "Edge": ("LOCALAPPDATA", "Microsoft/Edge/User Data"),
    "Chrome": ("LOCALAPPDATA", "Google/Chrome/User Data"),
    "Яндекс Браузер": ("LOCALAPPDATA", "Yandex/YandexBrowser/User Data"),
    "Brave": ("LOCALAPPDATA", "BraveSoftware/Brave-Browser/User Data"),
    "Opera": ("LOCALAPPDATA", "Opera Software/Opera Stable"),
    "Vivaldi": ("LOCALAPPDATA", "Vivaldi/User Data"),
}


def _env(key: str) -> Path | None:
    value = os.environ.get(key)
    return Path(value) if value else None


def _temp_roots() -> list[Path]:
    roots = []
    for key in ("TEMP", "TMP"):
        path = _env(key)
        if path and path.is_dir() and path not in roots:
            roots.append(path)
    windows_temp = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp"
    if windows_temp.is_dir() and windows_temp not in roots:
        roots.append(windows_temp)
    return roots


def _thumbnail_files() -> list[Path]:
    local = _env("LOCALAPPDATA")
    if not local:
        return []
    explorer = local / "Microsoft" / "Windows" / "Explorer"
    if not explorer.is_dir():
        return []
    return [item for item in explorer.glob("thumbcache_*.db") if item.is_file()]


def _shader_caches() -> list[Path]:
    local = _env("LOCALAPPDATA")
    if not local:
        return []
    candidates = [
        local / "D3DSCache",
        local / "NVIDIA" / "DXCache",
        local / "NVIDIA" / "GLCache",
        local / "AMD" / "DxCache",
        local / "AMD" / "GLCache",
    ]
    return [path for path in candidates if path.is_dir()]


def _browser_caches() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for label, (env_key, relative) in BROWSERS.items():
        base = _env(env_key)
        if not base:
            continue
        root = base / relative
        if not root.is_dir():
            continue
        if root.name == "Opera Stable":
            cache = root / "Cache"
            if cache.is_dir():
                found[f"browser:{label}"] = cache
            continue
        for profile in root.iterdir():
            if not profile.is_dir():
                continue
            for name in CACHE_NAMES:
                cache = profile / name
                if cache.is_dir() and cache.parent == profile:
                    found[f"browser:{label}:{profile.name}:{name}"] = cache
    return found


def _wu_download() -> Path | None:
    path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SoftwareDistribution" / "Download"
    return path if path.is_dir() else None


def _windows_old() -> Path | None:
    drive = os.environ.get("SystemDrive", "C:")
    path = Path(f"{drive}\\Windows.old")
    return path if path.is_dir() else None


def _managed_cache_roots(category: str) -> list[Path]:
    """Return narrow, documented Windows cache/log locations for optional cleanup."""
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    program_data = _env("ProgramData") or Path(os.environ.get("SystemDrive", "C:")) / "ProgramData"
    roots = {
        # Delivery Optimization cache is reproducible; Windows can download it again.
        "delivery_optimization": [program_data / "Microsoft" / "Windows" / "DeliveryOptimization" / "Cache"],
        # Only archived reports, never active queue or the diagnostic database.
        "wer_archive": [program_data / "Microsoft" / "Windows" / "WER" / "ReportArchive"],
        # Setup logs are useful for troubleshooting, but are not required after setup.
        "setup_logs": [system / "Panther", system / "Panther" / "UnattendGC"],
    }
    return [path for path in roots.get(category, []) if path.is_dir()]


WALK_WORKERS = 6  # подпапки считаем параллельно: на SSD скан быстрее в разы


def _walk_size(root: Path) -> tuple[int, int]:
    total = 0
    files = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, files


def _dir_size(path: Path) -> tuple[int, int]:
    """Размер папки: верхние подпапки обходятся параллельно."""
    dirs: list[Path] = []
    total = 0
    files = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                        files += 1
                except OSError:
                    continue
    except OSError:
        return 0, 0
    if len(dirs) == 1:
        part, count = _walk_size(dirs[0])
        return total + part, files + count
    if dirs:
        with ThreadPoolExecutor(max_workers=min(WALK_WORKERS, len(dirs))) as pool:
            for part, count in pool.map(_walk_size, dirs):
                total += part
                files += count
    return total, files


def _recycle_size() -> int:
    """Размер корзины считаем напрямую: без запуска PowerShell."""
    root = Path(f"{os.environ.get('SystemDrive', 'C:')}\\$Recycle.Bin")
    if not root.is_dir():
        return 0
    return _dir_size(root)[0]


def targets() -> list[dict]:
    """Каталог целей очистки: что показываем в интерфейсе."""
    items = [
        {
            "id": "temp",
            "name": "Временные файлы",
            "description": "Папки Temp пользователя и Windows. Установщики и приложения создают их заново.",
            "kind": "files",
            "risk": "safe",
        },
        {
            "id": "thumbnails",
            "name": "Кэш эскизов",
            "description": "Картинки предпросмотра в Проводнике. Windows построит их снова при необходимости.",
            "kind": "files",
            "risk": "safe",
        },
        {
            "id": "shader_cache",
            "name": "Кэш шейдеров видеокарты",
            "description": "Временные кэши DirectX и драйверов NVIDIA/AMD. Игры и драйверы создадут их заново; первый запуск игры после очистки может быть дольше.",
            "kind": "files",
            "risk": "safe",
        },
        {
            "id": "crash_dumps",
            "name": "Отчёты об аварийных сбоях приложений",
            "description": "Старые локальные дампы сбоев из пользовательских и Windows Temp. Не затрагивает сохранения, документы, браузерные данные и входы в аккаунты.",
            "kind": "files",
            "risk": "safe",
        },
        {
            "id": "delivery_optimization",
            "name": "Кэш оптимизации доставки Windows",
            "description": "Удаляет только кэш P2P-доставки обновлений. Windows загрузит нужные файлы повторно; очередь и установленные обновления не затрагиваются.",
            "kind": "files",
            "risk": "safe",
        },
        {
            "id": "wer_archive",
            "name": "Архив старых отчётов об ошибках Windows",
            "description": "Удаляет только архивированные отчёты WER. Активную очередь отправки и базу диагностики не затрагивает; старые отчёты для анализа сбоев будут потеряны.",
            "kind": "files",
            "risk": "caution",
        },
        {
            "id": "setup_logs",
            "name": "Журналы установки Windows",
            "description": "Старые логи Panther после установки/обновления Windows. Их удаление освобождает место, но лишает диагностических записей установки.",
            "kind": "files",
            "risk": "caution",
        },
        {
            "id": "browsers",
            "name": "Кэш браузеров",
            "description": "Только папки Cache у Edge, Chrome, Яндекса, Brave, Opera и Vivaldi. Пароли и закладки не трогаются.",
            "kind": "files",
            "risk": "safe",
        },
        {
            "id": "recycle",
            "name": "Корзина",
            "description": "Файлы, которые вы уже удалили. Восстановить их после очистки не получится.",
            "kind": "recycle",
            "risk": "caution",
        },
        {
            "id": "wu_download",
            "name": "Загруженные обновления",
            "description": "Папка SoftwareDistribution\\Download. Уже установленные обновления остаются в системе.",
            "kind": "files",
            "risk": "caution",
        },
        {
            "id": "windows_old",
            "name": "Windows.old",
            "description": "Копия предыдущей установки Windows после обновления. Освобождает много места, "
                           "но вернуться к старой системе будет нельзя.",
            "kind": "windows_old",
            "risk": "danger",
        },
        {
            "id": "dism",
            "name": "Устаревшие компоненты Windows",
            "description": "DISM удаляет заменённые системные компоненты. Занимает 10–30 минут и не мешает работе.",
            "kind": "dism",
            "risk": "caution",
        },
    ]
    return items


def _scan_one(item: dict, temp_roots: list[Path]) -> dict:
    size = None
    files = None
    note = ""
    try:
        if item["id"] == "temp":
            size = 0
            files = 0
            sizes = [_dir_size(root) for root in temp_roots]
            for part, count in sizes:
                size += part
                files += count
        elif item["id"] == "thumbnails":
            cache = _thumbnail_files()
            size = sum(f.stat().st_size for f in cache if f.exists())
            files = len(cache)
        elif item["id"] == "shader_cache":
            size = files = 0
            for cache in _shader_caches():
                part, count = _dir_size(cache)
                size += part
                files += count
        elif item["id"] == "crash_dumps":
            dumps = [file for root in _temp_roots() for file in root.rglob("*.dmp") if file.is_file()]
            size = sum(file.stat().st_size for file in dumps if file.exists())
            files = len(dumps)
        elif item["id"] in {"delivery_optimization", "wer_archive", "setup_logs"}:
            size = files = 0
            for root in _managed_cache_roots(item["id"]):
                part, count = _dir_size(root)
                size += part
                files += count
        elif item["id"] == "browsers":
            size = 0
            files = 0
            cache_dirs = list(_browser_caches().values())
            if not cache_dirs:
                note = "Браузеры не найдены"
            for part, count in (_dir_size(cache) for cache in cache_dirs):
                size += part
                files += count
        elif item["id"] == "recycle":
            size = _recycle_size()
        elif item["id"] == "wu_download":
            target = _wu_download()
            if target:
                size, files = _dir_size(target)
            else:
                note = "Папка не найдена"
        elif item["id"] == "windows_old":
            target = _windows_old()
            if target:
                size, files = _dir_size(target)
            else:
                note = "Windows.old отсутствует — экономить нечего"
        elif item["id"] == "dism":
            note = "Размер заранее неизвестен"
    except Exception as exc:  # noqa: BLE001 - одна цель не должна ломать скан
        logger.warning("Скан %s: %s", item["id"], exc)
        note = "Не удалось посчитать"
    return {**item, "size": size, "files": files, "note": note}


def scan(job: dict | None = None) -> list[dict]:
    """Считает размер каждой цели. Ничего не удаляет. Цели идут параллельно."""
    items = targets()
    temp_roots = _temp_roots()
    if job is not None:
        jobs.update_progress(job, 0, "Подготовка категорий очистки…")
    results = []
    with ThreadPoolExecutor(max_workers=min(6, len(items))) as pool:
        futures = [pool.submit(_scan_one, item, temp_roots) for item in items]
        for index, future in enumerate(futures, 1):
            results.append(future.result())
            if job is not None:
                jobs.update_progress(job, index * 100 / max(1, len(items)), f"Проверено категорий: {index} из {len(items)}")
    return results


def _skip(path: Path) -> bool:
    text = str(path).lower()
    if "_mei" in text:
        return True  # распакованный onefile — удалять нельзя, приложение работает из него
    try:
        return (os.path.getmtime(path)) > (time.time() - OLD_FILE_SECONDS)
    except OSError:
        return True


def _remove_entry(target: Path, is_dir: bool) -> tuple[int, int]:
    if _skip(target):
        return 0, 0
    try:
        if is_dir:
            size, _ = _dir_size(target)
            shutil.rmtree(target, ignore_errors=False)
            return size, 0
        size = os.stat(target, follow_symlinks=False).st_size
        os.unlink(target)
        return size, 0
    except OSError:
        return 0, 1


def _clear_dir(path: Path) -> tuple[int, int]:
    """Удаляет содержимое папки, не трогая свежие файлы. Возвращает (байт, ошибок)."""
    entries = []
    try:
        with os.scandir(path) as scan:
            for entry in scan:
                try:
                    entries.append((Path(entry.path), entry.is_dir(follow_symlinks=False)))
                except OSError:
                    continue
    except OSError:
        return 0, 1

    freed = 0
    errors = 0
    if len(entries) > 1:
        with ThreadPoolExecutor(max_workers=min(WALK_WORKERS, len(entries))) as pool:
            for part, err in pool.map(lambda item: _remove_entry(*item), entries):
                freed += part
                errors += err
    else:
        for item in entries:
            part, err = _remove_entry(*item)
            freed += part
            errors += err
    return freed, errors


def _clear_windows_old(path: Path) -> int:
    """Удаляет Windows.old через takeown + rd. Только для строго проверенного пути."""
    root = Path(os.environ.get("SystemRoot", r"C:\Windows")).parent.resolve()
    if path.resolve() != root / "Windows.old":
        raise RuntimeError("Неожиданный путь Windows.old — удаление отменено")
    size, _ = _dir_size(path)
    subprocess.run(["takeown", "/f", str(path), "/r", "/d", "y"], capture_output=True, creationflags=CREATE_NO_WINDOW)
    subprocess.run(
        ["icacls", str(path), "/grant", "*S-1-5-32-544:F", "/t", "/c", "/q"],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )
    subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(path)], capture_output=True, creationflags=CREATE_NO_WINDOW)
    if path.exists():
        raise RuntimeError("Часть файлов Windows.old защищена системой — удалите её через «Очистку диска»")
    return size


def clean(ids: list[str], job: dict | None = None) -> dict:
    """Чистит выбранные цели. Возвращает освобождённые байты и отчёт по каждой."""
    available = {item["id"]: item for item in targets()}
    unknown = [item for item in ids if item not in available]
    if unknown:
        raise ValueError(f"Неизвестные цели очистки: {', '.join(unknown)}")

    report = []
    total = 0
    if job is not None:
        jobs.update_progress(job, 0, "Подготовка выбранных категорий…")
    for index, item_id in enumerate(ids, 1):
        item = available[item_id]
        if job is not None:
            jobs.update_progress(job, (index - 1) * 100 / max(1, len(ids)), f"Очистка: {item['name']} ({index} из {len(ids)})")
        freed = 0
        errors = 0
        note = ""
        try:
            if item_id == "temp":
                for root in _temp_roots():
                    part, err = _clear_dir(root)
                    freed += part
                    errors += err
            elif item_id == "thumbnails":
                for cache_file in _thumbnail_files():
                    if _skip(cache_file):
                        continue
                    try:
                        size = cache_file.stat().st_size
                        cache_file.unlink()
                        freed += size
                    except OSError:
                        errors += 1
            elif item_id == "shader_cache":
                for cache in _shader_caches():
                    part, err = _clear_dir(cache)
                    freed += part
                    errors += err
            elif item_id == "crash_dumps":
                for root in _temp_roots():
                    try:
                        candidates = root.rglob("*.dmp")
                        for dump in candidates:
                            if _skip(dump):
                                continue
                            part, err = _remove_entry(dump, False)
                            freed += part
                            errors += err
                    except OSError:
                        errors += 1
            elif item_id in {"delivery_optimization", "wer_archive", "setup_logs"}:
                for root in _managed_cache_roots(item_id):
                    part, err = _clear_dir(root)
                    freed += part
                    errors += err
            elif item_id == "browsers":
                for cache in _browser_caches().values():
                    part, err = _clear_dir(cache)
                    freed += part
                    errors += err
                note = "Закройте браузеры, чтобы освободить всё"
            elif item_id == "recycle":
                powershell.run("Clear-RecycleBin -Force -ErrorAction SilentlyContinue", timeout=120)
                note = "Корзина очищена"
            elif item_id == "wu_download":
                target = _wu_download()
                if target:
                    part, err = _clear_dir(target)
                    freed += part
                    errors += err
                else:
                    note = "Папка не найдена"
            elif item_id == "windows_old":
                target = _windows_old()
                freed = _clear_windows_old(target) if target else 0
                note = "Windows.old удалён" if target else "Windows.old отсутствует"
            elif item_id == "dism":
                note = "DISM запущен в фоне — см. журнал"
                if job is not None:
                    jobs.update_progress(job, None, "DISM очищает хранилище компонентов Windows…")
                result = subprocess.run(
                    ["dism.exe", "/online", "/cleanup-image", "/startcomponentcleanup"],
                    capture_output=True,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=3600,
                )
                if result.returncode != 0:
                    errors += 1
                    note = "DISM завершился с ошибкой — подробности в логе"
        except Exception as exc:  # noqa: BLE001 - отчёт по каждой цели
            logger.warning("Очистка %s: %s", item_id, exc)
            errors += 1
            note = str(exc)
        total += freed
        report.append({"id": item_id, "name": item["name"], "freed": freed, "errors": errors, "note": note})
        if job is not None:
            jobs.update_progress(job, index * 100 / max(1, len(ids)), f"Готово: {item['name']} ({index} из {len(ids)})")
        logger.info("Очистка %s: %.1f МБ, ошибок %d", item_id, freed / 1048576, errors)
    return {"freed": total, "report": report}


def data_dir() -> Path:
    return DATA_DIR
