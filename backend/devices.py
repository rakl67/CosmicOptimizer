"""Видеокарты и PnP-устройства через PowerShell (без внешних модулей)."""
from __future__ import annotations

import json
import re
import subprocess

from .config import logger

CREATE_NO_WINDOW = 0x08000000
INSTANCE_RE = re.compile(r"^[A-Za-z0-9\\&_.\-{}\[\]:#]+$")

PS_PREFIX = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
PS_LIST = (
    PS_PREFIX +
    "$ErrorActionPreference='SilentlyContinue';"
    "Get-PnpDevice -Class Display -PresentOnly | "
    "Select-Object FriendlyName,Status,InstanceId,Class,Problem | ConvertTo-Json -Compress"
)


def _powershell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )


def list_devices() -> list[dict]:
    result = _powershell(PS_LIST)
    raw = (result.stdout or "").strip()
    if not raw:
        logger.warning("Get-PnpDevice не вернул данных: %s", (result.stderr or "").strip())
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Не удалось разобрать вывод Get-PnpDevice")
        return []
    if isinstance(data, dict):
        data = [data]
    devices = []
    for item in data:
        instance = (item.get("InstanceId") or "").strip()
        if not instance or not INSTANCE_RE.match(instance):
            continue
        devices.append(
            {
                "name": item.get("FriendlyName") or "Неизвестное устройство",
                "status": item.get("Status") or "Unknown",
                "instance_id": instance,
                "problem": item.get("Problem"),
            }
        )
    return devices


def validate_instance(instance_id: str) -> str:
    instance_id = (instance_id or "").strip()
    if len(instance_id) > 260 or not INSTANCE_RE.match(instance_id):
        raise ValueError("Некорректный InstanceId устройства")
    return instance_id


def set_device_state(instance_id: str, enable: bool) -> dict:
    instance_id = validate_instance(instance_id)
    verb = "Enable-PnpDevice" if enable else "Disable-PnpDevice"
    command = (
        PS_PREFIX +
        f"$ErrorActionPreference='Stop'; {verb} -InstanceId '{instance_id}' -Confirm:$false; "
        f"Get-PnpDevice -InstanceId '{instance_id}' | Select-Object Status | ConvertTo-Json -Compress"
    )
    logger.info("%s: %s", verb, instance_id)
    result = _powershell(command)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "PowerShell завершился с ошибкой").strip()
        raise RuntimeError(f"Не удалось изменить устройство: {message[:400]}")
    status = ""
    try:
        status = json.loads((result.stdout or "").strip() or "{}").get("Status", "")
    except json.JSONDecodeError:
        pass
    return {"instance_id": instance_id, "enabled": enable, "status": status}
