"""Cosmic Optimizer — локальный оптимизатор Windows на pywebview."""
from __future__ import annotations

import ctypes
import functools
import json
import os
import subprocess
import platform
import shutil
import socket
import sys
import winreg
from datetime import datetime
from pathlib import Path

import webview

from backend import (
    admin,
    backup,
    benchmark,
    cleanup,
    config,
    devices,
    jobs,
    maintenance,
    measure,
    monitor,
    power,
    registry,
    portable_profile,
    scripts,
    search,
    telemetry,
    tools,
)
from backend.config import logger
from backend.tweaks_catalog import CATEGORIES, RISK_LABELS, TWEAKS, tweak_by_id


def api_method(func):
    """Оборачивает метод API в {ok, data, error} и логирует исключения."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return {"ok": True, "data": func(self, *args, **kwargs), "error": None}
        except Exception as exc:  # noqa: BLE001 - граница UI/backend
            logger.exception("Ошибка в %s", func.__name__)
            message = str(exc).strip() or exc.__class__.__name__
            return {"ok": False, "data": None, "error": message}

    return wrapper


def _windows_version() -> dict:
    info = {"product": platform.platform(), "version": "", "build": "", "edition": ""}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            def value(name):
                try:
                    return str(winreg.QueryValueEx(key, name)[0])
                except OSError:
                    return ""
            info["edition"] = value("ProductName")
            info["version"] = value("DisplayVersion")
            build = value("CurrentBuild")
            ubr = value("UBR")
            info["build"] = f"{build}.{ubr}" if ubr else build
    except OSError:
        pass
    return info


def _log_tail(limit: int) -> list[str]:
    try:
        with config.LOG_FILE.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return [line.rstrip("\n") for line in lines[-limit:]]
    except OSError:
        return []


def _last_backup() -> dict | None:
    items = backup.list_backups()
    return items[0] if items else None


def _tweak_payload(tweak: dict) -> dict:
    state = registry.get_state(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"])
    exists, current, _ = registry.read_value(tweak["key_path"], tweak["value_name"])
    return {
        **tweak,
        "risk_label": RISK_LABELS.get(tweak["risk"], tweak["risk"]),
        "state": state,
        "current": str(current) if exists and current is not None else None,
    }


class Api:
    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._pending_profile_import: dict | None = None

    def bind(self, window: webview.Window) -> None:
        self._window = window

    @api_method
    def get_system_info(self) -> dict:
        version = _windows_version()
        return {
            "app_version": config.VERSION,
            "app_author": config.AUTHOR,
            "os": version["product"],
            "edition": version["edition"],
            "version": version["version"],
            "build": version["build"],
            "hostname": socket.gethostname(),
            "user": os.environ.get("USERNAME", ""),
            "admin": admin.is_admin(),
            "arch": platform.machine(),
            "executable": sys.executable,
        }

    @api_method
    def get_dashboard(self) -> dict:
        settings = config.load_settings()
        states = [t for t in TWEAKS if registry.get_state(t["key_path"], t["value_name"], t["on_value"], t["off_value"]) == "on"]
        return {
            "system": self.get_system_info()["data"],
            "last_backup": _last_backup(),
            "logs": _log_tail(10),
            "settings": settings,
            "tweaks_total": len(TWEAKS),
            "tweaks_on": len(states),
            "tweaks_on_names": [t["name"] for t in states],
            "paths": {
                "logs": str(config.LOGS_DIR),
                "backups": str(config.backups_dir()),
                "data": str(config.DATA_DIR),
            },
        }

    @api_method
    def list_tweaks(self) -> dict:
        return {
            "categories": CATEGORIES,
            "tweaks": [_tweak_payload(tweak) for tweak in TWEAKS],
            "admin": admin.is_admin(),
        }

    @api_method
    def get_telemetry_status(self) -> dict:
        return telemetry.status()

    @api_method
    def apply_telemetry_control(self, control_id: str) -> dict:
        return telemetry.apply_control(control_id)

    @api_method
    def restore_telemetry_control(self, control_id: str) -> dict:
        return telemetry.restore_control(control_id)

    @api_method
    def apply_telemetry_profile(self) -> dict:
        return telemetry.apply_profile()

    @api_method
    def restore_telemetry_profile(self) -> dict:
        return telemetry.restore_profile()

    @api_method
    def apply_tweak(self, tweak_id: str) -> dict:
        tweak = tweak_by_id(tweak_id)
        if tweak["requires_admin"] and not admin.is_admin():
            raise RuntimeError("Для этого твика нужны права администратора")
        state = registry.get_state(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"])
        if state == "missing":
            raise RuntimeError("Ключ реестра отсутствует на этой системе — твик недоступен")
        if state == "on":
            return {"id": tweak_id, "state": "on", "changed": False, "message": "Уже включено"}

        prev_exists, prev_value, _ = registry.read_value(tweak["key_path"], tweak["value_name"])
        backup.backup_before_change(tweak)
        registry.write_value(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["value_type"])
        backup.record_action(
            {
                "type": "tweak",
                "id": tweak_id,
                "name": tweak["name"],
                "direction": "on",
                "prev_exists": prev_exists,
                "prev_value": prev_value if prev_exists else None,
            }
        )
        logger.info("Применён твик: %s (%s)", tweak["name"], tweak_id)
        return {
            "id": tweak_id,
            "state": "on",
            "changed": True,
            "restart": tweak["restart"],
            "message": f"«{tweak['name']}» применён" + (" — нужна перезагрузка" if tweak["restart"] else ""),
        }

    @api_method
    def revert_tweak(self, tweak_id: str) -> dict:
        tweak = tweak_by_id(tweak_id)
        if tweak["requires_admin"] and not admin.is_admin():
            raise RuntimeError("Для этого твика нужны права администратора")
        state = registry.get_state(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"])
        if state == "missing":
            raise RuntimeError("Ключ реестра отсутствует на этой системе — откатывать нечего")
        if state == "off":
            return {"id": tweak_id, "state": "off", "changed": False, "message": "Уже выключено"}

        prev_exists, prev_value, _ = registry.read_value(tweak["key_path"], tweak["value_name"])
        backup.backup_before_change(tweak)
        registry.write_value(tweak["key_path"], tweak["value_name"], tweak["off_value"], tweak["value_type"])
        backup.record_action(
            {
                "type": "tweak",
                "id": tweak_id,
                "name": tweak["name"],
                "direction": "off",
                "prev_exists": prev_exists,
                "prev_value": prev_value if prev_exists else None,
            }
        )
        logger.info("Откачен твик: %s (%s)", tweak["name"], tweak_id)
        return {
            "id": tweak_id,
            "state": "off",
            "changed": True,
            "restart": tweak["restart"],
            "message": f"«{tweak['name']}» откачен" + (" — нужна перезагрузка" if tweak["restart"] else ""),
        }

    @api_method
    def apply_category(self, category: str) -> dict:
        if category not in {item["id"] for item in CATEGORIES}:
            raise ValueError("Неизвестная категория")
        results = []
        for tweak in TWEAKS:
            if tweak["category"] != category:
                continue
            try:
                results.append(self.apply_tweak(tweak["id"]))
            except Exception as exc:  # noqa: BLE001 - категория обрабатывается целиком
                results.append({"ok": False, "error": str(exc), "data": {"id": tweak["id"]}})
        done = sum(1 for item in results if item.get("ok"))
        return {"applied": done, "total": len(results), "results": results}

    @api_method
    def revert_category(self, category: str) -> dict:
        if category not in {item["id"] for item in CATEGORIES}:
            raise ValueError("Неизвестная категория")
        results = []
        for tweak in TWEAKS:
            if tweak["category"] != category:
                continue
            try:
                results.append(self.revert_tweak(tweak["id"]))
            except Exception as exc:  # noqa: BLE001
                results.append({"ok": False, "error": str(exc), "data": {"id": tweak["id"]}})
        done = sum(1 for item in results if item.get("ok"))
        return {"reverted": done, "total": len(results), "results": results}

    @api_method
    def list_devices(self) -> dict:
        return {"devices": devices.list_devices(), "admin": admin.is_admin()}

    @api_method
    def set_device(self, instance_id: str, enable: bool) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Управление устройствами доступно только от администратора")
        instance_id = devices.validate_instance(instance_id)

        snapshot = config.backups_dir() / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_devices"
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "devices.json").write_text(
            json.dumps(devices.list_devices(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (snapshot / "meta.json").write_text(
            json.dumps(
                {
                    "type": "devices",
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "note": f"Список устройств перед {'включением' if enable else 'отключением'} {instance_id}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        result = devices.set_device_state(instance_id, enable)
        logger.info("Устройство %s: %s", instance_id, "включено" if enable else "отключено")
        return result

    @api_method
    def list_scripts(self) -> dict:
        return {"scripts": scripts.list_scripts(), "admin": admin.is_admin()}

    @api_method
    def run_script(self, name: str) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Скрипты запускаются только от администратора")
        return scripts.run_script(name)

    @api_method
    def revert_script(self, name: str) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Откат скриптов доступен только от администратора")
        result = scripts.revert_script(name)
        result["message"] = f"Откат выполнен: {name}"
        return result

    @api_method
    def list_tools(self) -> dict:
        return {
            "tools": tools.tools_catalog(),
            "downloads": str(tools.DOWNLOAD_DIR),
            "gpu": tools.gpu_vendor(),
            "admin": admin.is_admin(),
        }

    @api_method
    def download_tool(self, tool_id: str) -> dict:
        return tools.download_tool(tool_id)

    @api_method
    def open_tool_link(self, tool_id: str) -> dict:
        return tools.open_link(tool_id)

    @api_method
    def run_debloat(self) -> dict:
        return tools.run_debloat()

    @api_method
    def get_metrics(self) -> dict:
        return monitor.metrics()

    @api_method
    def junk_targets(self) -> dict:
        return {"targets": cleanup.targets()}

    @api_method
    def scan_junk(self) -> dict:
        job = jobs.start_task("Сканирование мусора", lambda task: cleanup.scan(task))
        return {"job": job["id"], "title": job["title"]}

    @api_method
    def clean_junk(self, ids: list) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Очистка требует прав администратора")
        if not isinstance(ids, list) or not ids:
            raise ValueError("Не выбрано ни одной категории")
        known = {item["id"] for item in cleanup.targets()}
        selected = [str(item) for item in ids]
        unknown = [item for item in selected if item not in known]
        if unknown:
            raise ValueError(f"Неизвестная категория: {unknown[0]}")
        jobs.cleanup_old()
        job = jobs.start_task("Очистка мусора", lambda task: cleanup.clean(selected, task))
        return {"job": job["id"], "title": job["title"]}

    @api_method
    def job_status(self, job_id: str) -> dict:
        return jobs.status(job_id)

    @api_method
    def disk_info(self) -> dict:
        return maintenance.disk_info()

    @api_method
    def ping_host(self, host: str) -> dict:
        """Явная проверка доступности/задержки до указанного пользователем узла."""
        return maintenance.ping_host(str(host or ""))

    @api_method
    def start_trim(self) -> dict:
        if not admin.is_admin():
            raise RuntimeError("TRIM требует прав администратора")
        info = maintenance.disk_info()
        if not info.get("ssd_present"):
            raise RuntimeError("SSD не обнаружен — TRIM не требуется")
        job = jobs.start_process("TRIM системного диска", maintenance.trim_args(), timeout=1800)
        return {"job": job["id"], "title": job["title"]}

    @api_method
    def power_schemes(self) -> dict:
        return power.list_schemes()

    @api_method
    def activate_power_scheme(self, guid: str) -> dict:
        return power.activate(guid)

    @api_method
    def delete_power_scheme(self, guid: str) -> dict:
        return power.delete(guid)

    @api_method
    def start_benchmark(self, duration: int, drive: str) -> dict:
        duration = int(duration)
        if duration < 10 or duration > 60:
            raise ValueError("Выберите длительность от 10 до 60 секунд")
        job = jobs.start_task("Короткий тест диска", lambda task: benchmark.run(duration, drive, task))
        return {"job": job["id"], "title": job["title"]}

    @api_method
    def system_scan(self, kind: str) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Проверка системы требует прав администратора")
        args = maintenance.scan_args(str(kind))
        title = maintenance.SCAN_TITLES.get(str(kind), "Проверка системы")
        job = jobs.start_process(title, args, timeout=3600)
        return {"job": job["id"], "title": job["title"], "hint": "Это может занять 10–25 минут"}

    @api_method
    def list_measurements(self) -> dict:
        return {"items": measure.list_measurements()}

    @api_method
    def take_measurement(self) -> dict:
        return measure.take()

    @api_method
    def delete_measurement(self, measure_id: str) -> dict:
        return measure.delete(str(measure_id))

    @api_method
    def global_search(self, query: str) -> dict:
        return {"items": search.search(str(query or ""))}

    @api_method
    def finish_onboarding(self) -> dict:
        return config.save_settings({"onboarding_done": True})

    @api_method
    def reset_onboarding(self) -> dict:
        return config.save_settings({"onboarding_done": False})

    @api_method
    def create_backup(self) -> dict:
        try:
            device_list = devices.list_devices()
        except Exception as exc:  # noqa: BLE001 - бэкап важнее списка устройств
            logger.warning("Не удалось получить список устройств: %s", exc)
            device_list = []
        result = backup.create_backup(devices=device_list)
        return result

    @api_method
    def list_backups(self) -> dict:
        return {"backups": backup.list_backups(), "dir": str(config.backups_dir())}

    @api_method
    def create_restore_point(self) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Точка восстановления создаётся только от администратора")
        result = backup.create_restore_point("Cosmic Optimizer")
        result["message"] = f"Точка восстановления создана ({result.get('time') or 'без времени'})"
        return result

    @api_method
    def reboot_now(self) -> dict:
        """Запрашивает немедленную перезагрузку после явного выбора пользователя в интерфейсе."""
        subprocess.Popen(["shutdown.exe", "/r", "/t", "0", "/c", "Перезагрузка после применения профиля Cosmic Optimizer"], creationflags=0x08000000)
        return {"scheduled": True}

    @api_method
    def list_restore_points(self) -> dict:
        try:
            return {"points": backup.list_restore_points(10), "admin": admin.is_admin()}
        except Exception as exc:  # noqa: BLE001 - список не критичен
            logger.warning("Не удалось получить точки восстановления: %s", exc)
            return {"points": [], "admin": admin.is_admin()}

    @api_method
    def restore_backup(self, name: str) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Восстановление реестра доступно только от администратора")
        return backup.restore_backup(name)

    @api_method
    def delete_backup(self, name: str) -> dict:
        return backup.delete_backup(name)

    @api_method
    def export_portable_profile(self) -> dict:
        if self._window is None:
            raise RuntimeError("Окно приложения ещё не готово")
        selected = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=f"CosmicProfile_{datetime.now():%Y-%m-%d}.cosmicprofile",
            file_types=("Профиль Cosmic Optimizer (*.cosmicprofile)",),
        )
        if not selected:
            return {"cancelled": True}
        result = portable_profile.export_profile(Path(selected[0]), portable_profile.detect_gpu_vendors())
        return {**result, "cancelled": False}

    @api_method
    def select_portable_profile(self) -> dict:
        if self._window is None:
            raise RuntimeError("Окно приложения ещё не готово")
        self._pending_profile_import = None
        selected = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Профиль Cosmic Optimizer (*.cosmicprofile)",),
        )
        if not selected:
            self._pending_profile_import = None
            return {"cancelled": True}
        preview = portable_profile.read_profile(Path(selected[0]), portable_profile.detect_gpu_vendors())
        preview["filename"] = Path(selected[0]).name
        self._pending_profile_import = preview
        return {**preview, "profile": None, "cancelled": False}

    @api_method
    def apply_portable_profile(self) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Импорт профиля требует прав администратора")
        if self._pending_profile_import is None:
            raise RuntimeError("Сначала выберите и проверьте файл профиля")
        preview = self._pending_profile_import
        self._pending_profile_import = None
        current_vendors = portable_profile.detect_gpu_vendors()
        if set(current_vendors) != set(preview.get("local_vendors", [])):
            raise RuntimeError("Список видеокарт изменился после проверки. Выберите профиль ещё раз, чтобы пересчитать совместимость.")
        def apply(task):
            result = portable_profile.apply_profile(preview, task)
            result.update(
                {
                    "incompatible": preview["incompatible"],
                    "unavailable": preview["unavailable"],
                    "unknown": preview["unknown"],
                    "needs_restart": any(item["restart"] for item in result["applied"]),
                }
            )
            return result

        job = jobs.start_task("Импорт профиля", apply)
        return {"job": job["id"], "title": job["title"]}

    @api_method
    def undo_last(self) -> dict:
        if not admin.is_admin():
            raise RuntimeError("Откат изменений доступен только от администратора")
        entry = backup.pop_last_action()
        if not entry:
            raise RuntimeError("Нет действий для отката")
        if entry.get("type") == "tweak":
            tweak = tweak_by_id(entry["id"])
            backup.backup_before_change(tweak)
            if entry.get("prev_exists"):
                registry.write_value(
                    tweak["key_path"], tweak["value_name"], entry.get("prev_value"), tweak["value_type"]
                )
            else:
                registry.delete_value(tweak["key_path"], tweak["value_name"])
            logger.info("Отменено действие: %s (%s)", entry.get("name"), entry.get("id"))
            return {"message": f"Отменено: «{entry.get('name')}»", "tweak": entry.get("id")}
        if entry.get("type") == "script":
            result = scripts.undo_from_action(entry["id"])
            return {"message": f"Откачен скрипт: «{entry.get('name')}»", "script": result}

        raise RuntimeError(f"Неизвестный тип действия: {entry.get('type')}")

    @api_method
    def get_logs(self, limit: int = 400) -> dict:
        limit = max(10, min(int(limit), 5000))
        size = config.LOG_FILE.stat().st_size if config.LOG_FILE.exists() else 0
        return {"lines": _log_tail(limit), "path": str(config.LOG_FILE), "size": size}

    @api_method
    def get_log_text(self) -> dict:
        """Полный текст лога для копирования в буфер обмена."""
        try:
            text = config.LOG_FILE.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if len(text) > 2_000_000:
            text = text[-2_000_000:]
        return {"text": text, "path": str(config.LOG_FILE)}

    @api_method
    def clear_logs(self) -> dict:
        config.clear_log()
        logger.info("Лог очищен пользователем")
        return {"message": "Лог очищен"}

    @api_method
    def export_logs(self) -> dict:
        exports = config.DATA_DIR / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        target = exports / f"cosmic-optimizer-{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
        if config.LOG_FILE.exists():
            shutil.copy2(config.LOG_FILE, target)
        else:
            target.write_text("", encoding="utf-8")
        os.startfile(str(exports))  # noqa: S606 - локальная папка
        return {"path": str(target)}

    @api_method
    def get_settings(self) -> dict:
        return config.load_settings()

    @api_method
    def save_settings(self, settings: dict) -> dict:
        if not isinstance(settings, dict):
            raise ValueError("Некорректные настройки")
        if "backups_dir" in settings:
            raw = str(settings["backups_dir"]).strip()
            if not raw:
                raise ValueError("Путь к бэкапам не может быть пустым")
            path = Path(raw)
            if not path.is_absolute():
                raise ValueError("Укажите полный путь к папке бэкапов")
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".write_test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
            except OSError as exc:
                raise RuntimeError(f"Папка недоступна для записи: {exc}") from exc
            settings["backups_dir"] = raw
        saved = config.save_settings(settings)
        logger.info("Настройки сохранены")
        return saved

    @api_method
    def reset_settings(self) -> dict:
        saved = config.save_settings(dict(config.DEFAULT_SETTINGS))
        logger.info("Настройки сброшены")
        return saved

    @api_method
    def open_folder(self, kind: str) -> dict:
        paths = {
            "logs": config.LOGS_DIR,
            "backups": config.backups_dir(),
            "data": config.DATA_DIR,
            "scripts": config.SCRIPTS_DIR,
            "downloads": tools.DOWNLOAD_DIR,
        }
        path = paths.get(kind)
        if path is None:
            raise ValueError("Неизвестная папка")
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))  # noqa: S606
        return {"path": str(path)}

    @api_method
    def restart_as_admin(self) -> dict:
        admin.restart_as_admin()
        return {"message": "Запуск от администратора"}

    @api_method
    def quit_app(self) -> dict:
        if self._window is not None:
            self._window.destroy()
        return {"message": "Выход"}

    @api_method
    def uninstall_app(self) -> dict:
        if not config.FROZEN:
            raise RuntimeError("Полное удаление доступно только в собранной версии приложения")
        executable = Path(sys.executable).resolve()
        data_dir = config.DATA_DIR.resolve()
        if executable.name.casefold() != "cosmicoptimizer.exe" or executable.parent.name.casefold() != "dist":
            raise RuntimeError("Не удалось безопасно определить файл приложения для удаления")
        if data_dir.name.casefold() != "cosmicoptimizer":
            raise RuntimeError("Не удалось безопасно определить папку данных приложения")
        script = Path(os.environ.get("TEMP", str(Path.home()))) / f"cosmic-uninstall-{os.getpid()}.cmd"
        script.write_text(
            "@echo off\r\n"
            "ping 127.0.0.1 -n 4 >nul\r\n"
            f'del /f /q "{executable}"\r\n'
            f'rmdir /s /q "{data_dir}"\r\n'
            f'del /f /q "%~f0"\r\n',
            encoding="ascii",
        )
        subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=str(script.parent), creationflags=0x08000000 | subprocess.DETACHED_PROCESS)
        if self._window is not None:
            self._window.destroy()
        return {"scheduled": True}


def _fatal(message: str) -> None:
    """Показывает ошибку без консоли и пишет её в лог."""
    logger.error(message)
    try:
        ctypes.windll.user32.MessageBoxW(None, message, config.APP_NAME, 0x10)
    except (AttributeError, OSError):
        pass


def main() -> None:
    config.setup_logging()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

    elevated = admin.is_admin()
    # Без прав администратора показываем только экран-шлюз, а не рабочий интерфейс.
    index = config.ASSETS_DIR / ("index.html" if elevated else "gate.html")
    if not index.exists():
        _fatal(f"Не найден интерфейс приложения:\n{index}\n\nФайл повреждён или собран неправильно.")
        return

    config.prepare_scripts()
    try:
        config.SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    logger.info("Запуск Cosmic Optimizer %s (admin=%s, frozen=%s)", config.VERSION, elevated, config.FROZEN)

    api = Api()
    try:
        window = webview.create_window(
            config.APP_NAME,
            url=str(index),
            js_api=api,
            width=1200 if elevated else 560,
            height=800 if elevated else 420,
            min_size=(1000, 700) if elevated else (480, 380),
            resizable=elevated,
            background_color="#050505",
        )
    except Exception as exc:  # noqa: BLE001 - окно ещё не создано, показать диалог
        _fatal(f"Не удалось создать окно приложения:\n{exc}")
        return

    api.bind(window)
    if not elevated:
        logger.info("Прав администратора нет — показан экран запроса повышения")
    try:
        webview.start(debug=False)
    except Exception as exc:  # noqa: BLE001
        _fatal(
            "Не удалось запустить интерфейс.\n\n"
            "Скорее всего, не установлен Microsoft Edge WebView2 Runtime.\n"
            "Установите его с сайта Microsoft (Evergreen Bootstrapper) и запустите снова.\n\n"
            f"Техническая информация: {exc}"
        )
    logger.info("Приложение закрыто")


if __name__ == "__main__":
    main()
