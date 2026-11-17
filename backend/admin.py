"""Проверка и повышение прав администратора."""
from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def restart_as_admin() -> None:
    """Перезапускает приложение через UAC. Возвращается, только если запуск не удался."""
    if is_admin():
        return
    script = Path(sys.argv[0]).resolve()
    if getattr(sys, "frozen", False):
        params = subprocess.list2cmdline(sys.argv[1:])
        target = str(script)
    else:
        params = subprocess.list2cmdline([str(script), *sys.argv[1:]])
        target = sys.executable
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", target, params, str(script.parent), 1)
    if result <= 32:
        raise RuntimeError("Запуск от администратора отменён или недоступен")
