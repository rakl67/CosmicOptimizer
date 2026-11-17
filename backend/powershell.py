"""Единая обёртка над PowerShell для новых модулей."""
from __future__ import annotations

import json
import subprocess

CREATE_NO_WINDOW = 0x08000000
PREFIX = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='SilentlyContinue';"


def run(command: str, timeout: int = 90) -> str:
    """Выполняет PowerShell-команду и возвращает stdout в UTF-8."""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", PREFIX + command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0 and not (result.stdout or "").strip():
        message = (result.stderr or result.stdout or "PowerShell завершился с ошибкой").strip()
        raise RuntimeError(message[:400])
    return (result.stdout or "").strip()


def json_object(command: str, timeout: int = 90):
    """Выполняет команду и разбирает JSON-объект (пропуская служебные строки)."""
    raw = run(command, timeout)
    start = raw.find("{")
    if start < 0:
        return None
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError:
        return None
