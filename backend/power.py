"""Windows power scheme discovery and reversible-by-selection controls."""
from __future__ import annotations

import ctypes
import re
import subprocess

from .powershell import CREATE_NO_WINDOW

_SCHEME = re.compile(r"(?P<guid>[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\s*\((?P<name>.*?)\)")
_BUILTIN = {
    "381b4222-f694-41f0-9685-ff5bb260df2e",  # Balanced
    "a1841308-3541-4fab-bc81-f71556f20b4a",  # Power saver
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",  # High performance
    "e9a42b02-d5df-448d-aa00-03f14749eb61",  # Ultimate performance
}
_BUILTIN_NAMES = {
    "381b4222-f694-41f0-9685-ff5bb260df2e": "Сбалансированная",
    "a1841308-3541-4fab-bc81-f71556f20b4a": "Экономия энергии",
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": "Высокая производительность",
    "e9a42b02-d5df-448d-aa00-03f14749eb61": "Максимальная производительность",
}


def _run(*args: str) -> str:
    result = subprocess.run(
        ["powercfg.exe", *args], capture_output=True, text=False, timeout=30,
        creationflags=CREATE_NO_WINDOW,
    )
    # powercfg uses the active Windows console code page. On Russian Windows
    # this is commonly CP866; decoding its bytes as ANSI (CP1251) corrupts names.
    def decode(data: bytes | None) -> str:
        if not data:
            return ""
        try:
            oem_encoding = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:  # noqa: BLE001 - non-Windows fallback for static inspection
            oem_encoding = "cp866"
        for encoding in ("utf-8", oem_encoding, "mbcs"):
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("cp866", errors="replace")

    output = "\n".join(part for part in (decode(result.stdout), decode(result.stderr)) if part)
    if result.returncode:
        raise RuntimeError(output.strip()[-500:] or f"powercfg завершился с кодом {result.returncode}")
    return output


def list_schemes() -> dict:
    output = _run("/list")
    schemes = []
    for line in output.splitlines():
        match = _SCHEME.search(line)
        if not match:
            continue
        guid = match.group("guid").lower()
        schemes.append({
            "guid": guid,
            "name": _BUILTIN_NAMES.get(guid, match.group("name").strip()),
            "active": "*" in line[match.end():],
            "builtin": guid in _BUILTIN,
            "deletable": guid not in _BUILTIN and "*" not in line[match.end():],
        })
    if not schemes:
        raise RuntimeError("Windows не вернула список схем электропитания")
    active = next((item["guid"] for item in schemes if item["active"]), None)
    return {"schemes": schemes, "active_guid": active}


def activate(guid: str) -> dict:
    guid = str(guid or "").strip().lower()
    schemes = list_schemes()["schemes"]
    if not any(item["guid"] == guid for item in schemes):
        raise ValueError("Схема электропитания не найдена")
    _run("/setactive", guid)
    return list_schemes()


def delete(guid: str) -> dict:
    guid = str(guid or "").strip().lower()
    scheme = next((item for item in list_schemes()["schemes"] if item["guid"] == guid), None)
    if not scheme:
        raise ValueError("Схема электропитания не найдена")
    if not scheme["deletable"]:
        raise ValueError("Эту схему удалить нельзя: системные и активные схемы защищены")
    _run("/delete", guid)
    return list_schemes()
