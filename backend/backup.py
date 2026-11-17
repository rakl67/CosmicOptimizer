"""Бэкапы реестра/состояния и стек последних действий."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import admin, config, registry
from .config import logger
from .tweaks_catalog import TWEAKS

ACTIONS_LIMIT = 50
CREATE_NO_WINDOW = 0x08000000


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _safe_name(key_path: str) -> str:
    return key_path.replace("\\", "_").replace("{", "").replace("}", "").replace("*", "star")


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def tweak_states() -> dict:
    return {
        tweak["id"]: registry.get_state(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"])
        for tweak in TWEAKS
    }


def create_backup(note: str = "Полный бэкап", devices: list | None = None, progress=None) -> dict:
    """Полный бэкап: .reg всех доступных ключей + состояние твиков + устройства."""
    folder = config.backups_dir() / _stamp()
    suffix = 2
    while folder.exists():
        folder = config.backups_dir() / f"{_stamp()}_{suffix}"
        suffix += 1

    exported, failed = [], []
    total = max(1, len(TWEAKS))
    for index, tweak in enumerate(TWEAKS, 1):
        if progress:
            progress(index * 100 / total, f"Сохранение реестра: {index} из {len(TWEAKS)}")
        if not registry.key_exists(tweak["key_path"]):
            continue
        target = folder / "registry" / f"{_safe_name(tweak['key_path'])}.reg"
        try:
            registry.export_key(tweak["key_path"], target)
            exported.append(target.name)
        except Exception as exc:  # noqa: BLE001 - один ключ не должен ломать бэкап
            failed.append(f"{tweak['key_path']}: {exc}")

    meta = {
        "type": "backup",
        "created": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "states": tweak_states(),
        "exported": exported,
        "failed": failed,
        "devices": devices or [],
    }
    _write_json(folder / "meta.json", meta)
    logger.info("Бэкап создан: %s (ключей: %d)", folder.name, len(exported))
    return {"name": folder.name, "exported": len(exported), "failed": failed}


def backup_before_change(tweak: dict) -> Path | None:
    """Точечный .reg-бэкап ключа перед изменением. Возвращает папку действия."""
    if not config.load_settings().get("auto_backup", True):
        return None
    folder = config.backups_dir() / f"{_stamp()}_{tweak['id']}"
    target = folder / f"{_safe_name(tweak['key_path'])}.reg"
    registry.export_key(tweak["key_path"], target)
    _write_json(
        folder / "meta.json",
        {
            "type": "action",
            "created": datetime.now().isoformat(timespec="seconds"),
            "tweak": tweak["id"],
            "key": tweak["key_path"],
            "note": f"Бэкап ключа перед изменением «{tweak['name']}»",
        },
    )
    return folder


def list_backups() -> list[dict]:
    items = []
    root = config.backups_dir()
    if not root.exists():
        return items
    for folder in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        meta = _read_json(folder / "meta.json", {})
        items.append(
            {
                "name": folder.name,
                "type": meta.get("type", "action"),
                "created": meta.get("created", ""),
                "note": meta.get("note", ""),
                "tweak": meta.get("tweak"),
                "script": meta.get("script"),
                "reg_files": len(list(folder.rglob("*.reg"))),
                "has_state": bool(meta.get("states")),
            }
        )
    return items


def restore_backup(name: str) -> dict:
    root = config.backups_dir().resolve()
    folder = (root / name).resolve()
    if folder.parent != root or not folder.is_dir():
        raise ValueError("Некорректное имя бэкапа")
    files = sorted(folder.rglob("*.reg"))
    if not files:
        raise RuntimeError("В папке бэкапа нет .reg-файлов")
    restored, failed = 0, []
    for reg_file in files:
        try:
            registry.import_reg(reg_file)
            restored += 1
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{reg_file.name}: {exc}")
    logger.info("Восстановление %s: %d файлов, ошибок %d", name, restored, len(failed))
    return {"name": name, "restored": restored, "failed": failed}


def _load_actions() -> list[dict]:
    data = _read_json(config.ACTIONS_FILE, [])
    return data if isinstance(data, list) else []


def record_action(entry: dict) -> None:
    actions = _load_actions()
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    actions.append(entry)
    _write_json(config.ACTIONS_FILE, actions[-ACTIONS_LIMIT:])


def pop_last_action() -> dict | None:
    actions = _load_actions()
    if not actions:
        return None
    entry = actions.pop()
    _write_json(config.ACTIONS_FILE, actions)
    return entry


def delete_backup(name: str) -> dict:
    root = config.backups_dir().resolve()
    folder = (root / name).resolve()
    if folder.parent != root or not folder.is_dir():
        raise ValueError("Некорректное имя бэкапа")
    shutil.rmtree(folder)
    logger.info("Бэкап удалён: %s", name)
    return {"name": name}


_RESTORE_PS = r"""
$ErrorActionPreference = 'Stop'
$desc = '__DESC__'
$key = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore'
$had = $false
$old = 0
try {
  $old = (Get-ItemProperty -Path $key -Name SystemRestorePointCreationFrequency -ErrorAction Stop).SystemRestorePointCreationFrequency
  $had = $true
} catch {}
try { New-ItemProperty -Path $key -Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null } catch {}
$ok = $false
$err = ''
try {
  Checkpoint-Computer -Description $desc -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop
  $ok = $true
} catch {
  $err = $_.Exception.Message
  try {
    Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction Stop
    Checkpoint-Computer -Description $desc -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop
    $ok = $true
    $err = ''
  } catch { $err = $_.Exception.Message }
}
try {
  if ($had) { Set-ItemProperty -Path $key -Name SystemRestorePointCreationFrequency -Value $old }
  else { Remove-ItemProperty -Path $key -Name SystemRestorePointCreationFrequency -ErrorAction SilentlyContinue }
} catch {}
$made = $false
$time = ''
$seq = 0
try {
  $latest = Get-ComputerRestorePoint -ErrorAction Stop | Sort-Object SequenceNumber | Select-Object -Last 1
  if ($latest) {
    $seq = [int]$latest.SequenceNumber
    if ($latest.Description -eq $desc) { $made = $true }
    try { $time = $latest.ConvertToDateTime($latest.CreationTime).ToString('yyyy-MM-dd HH:mm:ss') } catch { $time = "$($latest.CreationTime)" }
  }
} catch {}
[pscustomobject]@{ ok = $ok; created = $made; error = $err; sequence = $seq; time = $time } | ConvertTo-Json -Compress
"""


def create_restore_point(description: str = "Cosmic Optimizer") -> dict:
    """Точка восстановления Windows. Обходит лимит 24 часа и включает защиту, если она выключена."""
    if not admin.is_admin():
        raise RuntimeError("Точка восстановления создаётся только от администратора")
    desc = " ".join(str(description).split())[:60] or "Cosmic Optimizer"
    desc = desc.replace("'", "").replace('"', "").replace("`", "")
    desc = f"{desc} {datetime.now():%Y-%m-%d %H:%M}"

    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + _RESTORE_PS.replace("__DESC__", desc),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        creationflags=CREATE_NO_WINDOW,
    )

    raw = (result.stdout or "").strip()
    data: dict = {}
    if raw:
        try:
            data = json.loads(raw.splitlines()[-1])
        except json.JSONDecodeError:
            data = {}

    if result.returncode != 0 and not data:
        detail = (result.stderr or raw or "PowerShell завершился с ошибкой").strip()
        logger.error("Точка восстановления: %s", detail[:300])
        raise RuntimeError(f"Не удалось создать точку восстановления: {detail[:300]}")

    if not data.get("ok"):
        detail = (data.get("error") or "").strip() or "Windows отклонил создание точки"
        logger.error("Точка восстановления не создана: %s", detail[:300])
        raise RuntimeError(f"Точка восстановления не создана: {detail[:300]}")

    if not data.get("created"):
        raise RuntimeError(
            "Windows сообщил об успехе, но новая точка не появилась. "
            "Проверьте «Защита системы» и свободное место на диске."
        )

    logger.info("Точка восстановления создана: %s (№%s)", data.get("time"), data.get("sequence"))
    return {
        "description": desc,
        "sequence": data.get("sequence"),
        "time": data.get("time"),
    }


def list_restore_points(limit: int = 10) -> list[dict]:
    """Последние точки восстановления Windows."""
    count = max(1, min(int(limit), 50))
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-ComputerRestorePoint | Sort-Object SequenceNumber | Select-Object -Last "
        f"{count} | ForEach-Object {{ [pscustomobject]@{{ seq=$_.SequenceNumber; "
        "desc=$_.Description; time=$_.ConvertToDateTime($_.CreationTime).ToString('yyyy-MM-dd HH:mm:ss') } } "
        "| ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=CREATE_NO_WINDOW,
    )
    raw = (result.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    points = [
        {
            "sequence": item.get("seq"),
            "description": item.get("desc") or "",
            "time": item.get("time") or "",
        }
        for item in data
    ]
    return list(reversed(points))
