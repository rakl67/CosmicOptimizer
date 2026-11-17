"""Замеры «до/после»: процессы, память, время загрузки, автозапуск."""
from __future__ import annotations

import json
from datetime import datetime

from . import monitor, powershell
from .config import DATA_DIR, logger

MEASURE_FILE = DATA_DIR / "measurements.json"
LIMIT = 30

BOOT_QUERY = (
    "$e=Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational';"
    "Id=100} -MaxEvents 1 -ErrorAction SilentlyContinue;"
    "$boot=$null;"
    "if($e){$x=[xml]$e.ToXml();$boot=($x.Event.EventData.Data | Where-Object { $_.Name -eq 'BootTime' }).'#text'};"
    "$startup=(Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue | Measure-Object).Count;"
    "[pscustomobject]@{boot_ms=$boot; startup=$startup} | ConvertTo-Json -Compress"
)


def _load() -> list[dict]:
    try:
        data = json.loads(MEASURE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEASURE_FILE.write_text(json.dumps(items[-LIMIT:], ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot() -> dict:
    """Снимает текущие показатели. Ничего не меняет в системе."""
    metrics = monitor.metrics()
    boot_ms = None
    startup = None
    try:
        data = powershell.json_object(BOOT_QUERY, timeout=45)
        if isinstance(data, dict):
            raw = data.get("boot_ms")
            boot_ms = int(float(raw)) if raw not in (None, "") else None
            startup = data.get("startup")
    except Exception as exc:  # noqa: BLE001 - журнал загрузки доступен не всегда
        logger.debug("Замер загрузки недоступен: %s", exc)

    return {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "created": datetime.now().isoformat(timespec="seconds"),
        "processes": metrics.get("processes"),
        "ram_percent": metrics.get("ram_percent"),
        "ram_used_mb": metrics.get("ram_used_mb"),
        "ram_total_mb": metrics.get("ram_total_mb"),
        "cpu": metrics.get("cpu"),
        "boot_ms": boot_ms,
        "startup": startup,
        "uptime": metrics.get("uptime"),
    }


def take() -> dict:
    item = snapshot()
    items = _load()
    items.append(item)
    _save(items)
    logger.info("Замер сохранён: процессов %s, ОЗУ %s МБ, загрузка %s мс", item["processes"], item["ram_used_mb"], item["boot_ms"])
    return {"measurement": item, "items": items}


def list_measurements() -> list[dict]:
    items = _load()
    prepared = []
    for index, item in enumerate(reversed(items)):
        previous = items[len(items) - 2 - index] if len(items) - 2 - index >= 0 else None
        entry = dict(item)
        entry["delta"] = _delta(previous, item) if previous else None
        prepared.append(entry)
    return prepared


def _delta(old: dict, new: dict) -> dict:
    def diff(key):
        before, after = old.get(key), new.get(key)
        if before is None or after is None:
            return None
        try:
            return round(float(after) - float(before), 1)
        except (TypeError, ValueError):
            return None

    return {
        "processes": diff("processes"),
        "ram_used_mb": diff("ram_used_mb"),
        "boot_ms": diff("boot_ms"),
        "startup": diff("startup"),
    }


def delete(measure_id: str) -> dict:
    items = [item for item in _load() if item.get("id") != measure_id]
    _save(items)
    return {"deleted": measure_id, "items": items}
