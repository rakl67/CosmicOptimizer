"""Чтение и запись реестра Windows без создания ключей «вслепую»."""
from __future__ import annotations

import subprocess
import winreg
from pathlib import Path

HIVES = {
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKU": winreg.HKEY_USERS,
}

TYPES = {
    "REG_SZ": winreg.REG_SZ,
    "REG_DWORD": winreg.REG_DWORD,
    "REG_QWORD": winreg.REG_QWORD,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
}

CREATE_NO_WINDOW = 0x08000000


def split_key(path: str) -> tuple[int, str]:
    hive_name, _, sub = path.partition("\\")
    hive = HIVES.get(hive_name.upper())
    if hive is None:
        raise ValueError(f"Неподдерживаемая ветка реестра: {hive_name}")
    if not sub:
        raise ValueError("Путь к ключу реестра пуст")
    return hive, sub


def key_exists(path: str) -> bool:
    try:
        hive, sub = split_key(path)
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ):
            return True
    except (OSError, ValueError):
        return False


def read_value(path: str, name: str) -> tuple[bool, object | None, int | None]:
    """Возвращает (значение существует, значение, тип)."""
    try:
        hive, sub = split_key(path)
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ) as key:
            try:
                value, vtype = winreg.QueryValueEx(key, name)
                return True, value, vtype
            except FileNotFoundError:
                return False, None, None
    except (OSError, ValueError):
        return False, None, None


def get_state(path: str, name: str, on_value, off_value) -> str:
    """Состояние твика: on / off / missing (ключа нет) / unknown."""
    if not key_exists(path):
        return "missing"
    exists, value, _ = read_value(path, name)
    if not exists:
        return "off"
    if value == on_value:
        return "on"
    if value == off_value:
        return "off"
    return "unknown"


def write_value(path: str, name: str, value, vtype: str) -> None:
    """Пишет значение. Ключ должен существовать — иначе понятная ошибка."""
    hive, sub = split_key(path)
    reg_type = TYPES.get(vtype, winreg.REG_DWORD)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, reg_type, value)
    except FileNotFoundError as exc:
        raise RuntimeError("Ключ реестра не найден — твик недоступен на этой системе") from exc
    except PermissionError as exc:
        raise RuntimeError("Нет прав на изменение ключа. Запустите приложение от администратора") from exc


def delete_value(path: str, name: str) -> None:
    hive, sub = split_key(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass
    except PermissionError as exc:
        raise RuntimeError("Нет прав на изменение ключа. Запустите приложение от администратора") from exc


def export_key(path: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["reg.exe", "export", path, str(target), "/y"],
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0 or not target.exists():
        message = (result.stderr or result.stdout or "reg export завершился с ошибкой").strip()
        raise RuntimeError(f"Не удалось создать .reg-бэкап: {message}")


def import_reg(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Файл бэкапа не найден: {path.name}")
    result = subprocess.run(
        ["reg.exe", "import", str(path)],
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "reg import завершился с ошибкой").strip()
        raise RuntimeError(f"Не удалось восстановить {path.name}: {message}")
