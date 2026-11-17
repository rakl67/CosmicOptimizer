"""Список, состояние и запуск пользовательских скриптов из scripts/ (включая scripts/материалы/)."""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from . import backup, config, registry
from .config import logger
from .scripts_catalog import script_meta

ALLOWED_EXT = {".bat", ".cmd", ".reg", ".ps1"}
CREATE_NO_WINDOW = 0x08000000
TIMEOUT = 1800
STATE_FILE = config.DATA_DIR / "scripts_state.json"

# Частые русские слова: по ним выбираем кодировку вывода между cp866 и cp1251.
_RU_HINTS = re.compile(
    r"успешн|операц|ошибк|не удал|не найден|файл|систем|ключ|значен|диск|доступ|путь|параметр",
    re.IGNORECASE,
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SECTION = re.compile(r"^\[(-?)(HKEY_[^\]]+)\]$")
_SETTING = re.compile(r'^(?:"([^"]*)"|(@))\s*=\s*(.*)$')


def _score(text: str) -> float:
    """Чем выше — тем больше похоже на нормальный русский текст."""
    score = len(_RU_HINTS.findall(text)) * 6.0
    score += sum(1 for ch in text if "\u0410" <= ch <= "\u044f") * 0.4
    score -= sum(1 for ch in text if ch < " " and ch not in "\t\r\n") * 12.0
    score -= text.count("\ufffd") * 8.0
    score -= sum(1 for ch in text if "\x80" <= ch <= "\x9f") * 6.0
    return score


def decode_output(raw: bytes) -> str:
    """Декодирует вывод консольных утилит: UTF-8, UTF-16, затем cp866 / cp1251 по смыслу."""
    if not raw:
        return ""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16").replace("\ufeff", "").strip()
        except UnicodeDecodeError:
            pass
    if raw.count(b"\x00") > len(raw) // 3:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                return raw.decode(enc).strip()
            except UnicodeDecodeError:
                continue
    best, best_score = "", float("-inf")
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        score = _score(text)
        if score > best_score:
            best, best_score = text, score
    return best.strip()


def clean_output(text: str) -> str:
    """Убирает управляющие символы, из-за которых лог выглядит мусором."""
    text = _CONTROL.sub("", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line.strip()).strip()


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
        if text.count("\x00") == 0:
            return text
    return raw.decode("cp1251", errors="replace")


def _decode_hex(text: str) -> str | None:
    """hex(2)/hex(1) — строка в UTF-16LE."""
    compact = text.replace(",", "").replace(" ", "")
    try:
        return bytes.fromhex(compact).decode("utf-16-le").rstrip("\x00")
    except (ValueError, UnicodeDecodeError):
        return None


def parse_reg(path: Path) -> list[dict] | None:
    """Возвращает список значений из .reg. None — если файл удаляет ключи или не разобран."""
    entries: list[dict] = []
    current: str | None = None
    for raw_line in _read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.lower().startswith("windows registry editor"):
            continue
        section = _SECTION.match(line)
        if section:
            if section.group(1) == "-":
                return None  # удаление ключа целиком — состояние не вычисляем
            current = section.group(2)
            continue
        if current is None:
            continue
        setting = _SETTING.match(line)
        if not setting:
            continue
        name = "" if setting.group(2) else setting.group(1)
        value = setting.group(3).strip()
        if value.startswith('"') and value.endswith('"'):
            entries.append({"key": current, "name": name, "type": "REG_SZ", "value": value[1:-1]})
        elif value.lower().startswith("dword:"):
            try:
                entries.append({"key": current, "name": name, "type": "REG_DWORD", "value": int(value[6:], 16)})
            except ValueError:
                return None
        elif value.lower().startswith("hex(2):") or value.lower().startswith("hex(1):"):
            text = _decode_hex(value.split(":", 1)[1])
            if text is None:
                return None
            entries.append({"key": current, "name": name, "type": "REG_SZ", "value": text})
        else:
            return None  # бинарные значения не сравниваем
    return entries or None


def _reg_state(path: Path) -> str:
    entries = parse_reg(path)
    if entries is None:
        return "unknown"
    matched = 0
    for entry in entries:
        if not registry.key_exists(entry["key"]):
            return "missing"
        exists, value, _ = registry.read_value(entry["key"], entry["name"])
        if exists and str(value) == str(entry["value"]):
            matched += 1
    if matched == len(entries):
        return "on"
    return "off"


def _load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(data: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _mark(name: str, applied: bool) -> None:
    data = _load_state()
    # Храним и откат: значение реестра после возврата к исходному иногда
    # совпадает с .reg-файлом, поэтому по одному реестру нельзя понять,
    # было ли действие приложения отменено.
    data[name] = {"applied": bool(applied), "ts": datetime.now().isoformat(timespec="seconds")}
    _save_state(data)


def _state_of(name: str, path: Path) -> str:
    if path.suffix.lower() == ".reg":
        marker = _load_state().get(name)
        if isinstance(marker, dict) and isinstance(marker.get("applied"), bool):
            return "on" if marker["applied"] else "off"
        return _reg_state(path)
    return "on" if _load_state().get(name, {}).get("applied") else "off"


def _required_vendor(name: str) -> str:
    upper = name.replace("\\", "/").upper()
    if "/AMD/" in upper or "/AMD " in upper:
        return "amd"
    if "/NVIDIA/" in upper or "/NVIDIA " in upper:
        return "nvidia"
    return ""


def _detected_vendors() -> set[str]:
    # Перепроверяем реальные присутствующие PnP-видеокарты, а не только имя профиля.
    from .portable_profile import detect_gpu_vendors
    return set(detect_gpu_vendors())


def _require_compatible_gpu(name: str) -> str:
    required = _required_vendor(name)
    if not required:
        return ""
    vendors = _detected_vendors()
    if required in vendors:
        return ""
    label = "AMD" if required == "amd" else "NVIDIA"
    if not vendors:
        raise RuntimeError(f"У вас не обнаружена видеокарта {label}. Этот скрипт можно применять только на системе с видеокартой {label}.")
    actual = " и ".join("AMD" if vendor == "amd" else "NVIDIA" if vendor == "nvidia" else "Intel" for vendor in sorted(vendors))
    raise RuntimeError(f"Обнаружена видеокарта {actual}; скрипт предназначен только для {label}.")


def list_scripts() -> list[dict]:
    root = config.SCRIPTS_DIR
    if not root.exists():
        return []
    detected = _detected_vendors()
    backed_up_reg_scripts = {
        item.get("script") for item in backup.list_backups()
        if item.get("type") == "script" and item.get("reg_files", 0) > 0 and item.get("script")
    }
    items = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXT:
            continue
        rel = path.relative_to(root).as_posix()
        meta = script_meta(rel)
        items.append(
            {
                "name": rel,
                "title": meta["title"],
                "description": meta["description"],
                "risk": meta["risk"],
                "restart": meta["restart"],
                "kind": path.suffix.lower().lstrip("."),
                "group": path.parent.relative_to(root).as_posix() or "scripts",
                "size": path.stat().st_size,
                "state": _state_of(rel, path),
                "can_revert": bool(meta.get("undo")) or (path.suffix.lower() == ".reg" and rel in backed_up_reg_scripts),
                "revert_reason": (
                    "Нет резервной копии реестра — безопасный откат недоступен"
                    if path.suffix.lower() == ".reg" and rel not in backed_up_reg_scripts
                    else ""
                ),
                "undo_label": meta.get("undo_label") or "Откатить",
                "modifies": meta.get("modifies") or "",
                "vendor": _required_vendor(rel),
                "vendor_compatible": not _required_vendor(rel) or _required_vendor(rel) in detected,
                "vendor_reason": (
                    f"У вас не обнаружена видеокарта {'AMD' if _required_vendor(rel) == 'amd' else 'NVIDIA'}"
                    if _required_vendor(rel) and _required_vendor(rel) not in detected and not detected
                    else f"Обнаружена другая видеокарта; требуется {'AMD' if _required_vendor(rel) == 'amd' else 'NVIDIA'}"
                    if _required_vendor(rel) and _required_vendor(rel) not in detected
                    else ""
                ),
            }
        )
    return items


def resolve_script(name: str) -> Path:
    """Принимает относительный путь внутри scripts/. Выход за папку запрещён."""
    raw = (name or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or ".." in raw.split("/"):
        raise ValueError("Некорректное имя скрипта")
    root = config.SCRIPTS_DIR.resolve()
    path = (root / raw).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError("Скрипт не найден")
    if path.suffix.lower() not in ALLOWED_EXT:
        raise ValueError("Неподдерживаемый тип файла")
    return path


def _command_for(path: Path) -> list[str]:
    ext = path.suffix.lower()
    if ext == ".reg":
        return ["reg.exe", "import", str(path)]
    if ext == ".ps1":
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    return [os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), "/c", str(path)]


def _backup_reg(path: Path, name: str) -> None:
    """Fail closed: импорт разрешён только после полного сохранения затронутых ключей."""
    entries = parse_reg(path)
    if not entries:
        raise RuntimeError("Импорт отменён: формат .reg не поддерживается для безопасного бэкапа")

    keys = list(dict.fromkeys(entry["key"] for entry in entries))
    missing_keys = [key for key in keys if not registry.key_exists(key)]
    if missing_keys:
        raise RuntimeError(
            "Импорт отменён: не удалось заранее сохранить отсутствующий ключ реестра: "
            + ", ".join(missing_keys[:3])
        )

    # Запоминаем отсутствовавшие значения: импорт .reg сам их не удаляет при откате.
    missing_values = []
    for entry in entries:
        exists, _, _ = registry.read_value(entry["key"], entry["name"])
        if not exists:
            missing_values.append({"key": entry["key"], "name": entry["name"]})

    root = config.backups_dir()
    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", name)[-40:].strip("-") or "script"
    base = f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{safe_name}"
    folder = root / base
    suffix = 2
    while folder.exists():
        folder = root / f"{base}_{suffix}"
        suffix += 1

    try:
        folder.mkdir(parents=True, exist_ok=False)
        for index, key in enumerate(keys, 1):
            safe_key = re.sub(r'[<>:"/\\|?*]+', "_", key).replace("{", "").replace("}", "")
            target = folder / "registry" / f"{index:03d}_{safe_key}.reg"
            registry.export_key(key, target)
        (folder / "meta.json").write_text(
            json.dumps(
                {
                    "type": "script",
                    "script": name,
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "note": f"Бэкап ключей перед запуском «{name}»",
                    "missing_values": missing_values,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - без полного бэкапа изменять реестр нельзя
        raise RuntimeError(f"Импорт отменён: не удалось полностью сохранить реестр перед применением: {exc}") from exc
    logger.info("Бэкап перед скриптом %s: %d ключей", name, len(keys))


def run_script(name: str) -> dict:
    path = resolve_script(name)
    _require_compatible_gpu(name)
    ext = path.suffix.lower()
    logger.info("Запуск: %s", name)
    if ext == ".reg":
        _backup_reg(path, name)

    try:
        result = subprocess.run(
            _command_for(path),
            cwd=str(path.parent),
            capture_output=True,
            timeout=TIMEOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("Скрипт %s превысил лимит %d с и был прерван", name, TIMEOUT)
        raise RuntimeError(f"Скрипт выполняется дольше {TIMEOUT // 60} минут и был прерван") from exc

    output = clean_output(decode_output((result.stdout or b"") + (result.stderr or b"")))
    if len(output) > 8000:
        output = output[:8000] + "\n… вывод обрезан"

    if result.returncode == 0:
        _mark(name, True)
        backup.record_action({"type": "script", "id": name, "name": name})
        if ext == ".reg":
            logger.info("Файл реестра применён: %s", name)
            output = output or "Импорт реестра выполнен успешно."
        else:
            logger.info("Скрипт завершён: %s (код 0)", name)
            if output:
                logger.info("Вывод %s:\n%s", name, output)
    else:
        logger.warning("Скрипт завершён с ошибкой: %s (код %d)", name, result.returncode)
        if output:
            logger.warning("Вывод %s:\n%s", name, output)

    return {
        "name": name,
        "returncode": result.returncode,
        "output": output or "Скрипт не вывел данных.",
        "state": _state_of(name, path),
    }


def _revert_reg(name: str) -> dict:
    backups = [b for b in backup.list_backups() if b.get("tweak") == name or b.get("script") == name]
    if not backups:
        raise RuntimeError("Нет бэкапа этого файла: запустите его через приложение, тогда откат станет доступен")
    root = config.backups_dir()
    folder = root / backups[0]["name"]
    files = sorted(folder.rglob("*.reg"))
    if not files:
        raise RuntimeError("В бэкапе нет .reg-файлов для восстановления")
    for reg_file in files:
        registry.import_reg(reg_file)
    meta = {}
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    source_entries = parse_reg(resolve_script(name)) or []
    source_pairs = {(entry["key"], entry["name"]) for entry in source_entries}
    missing_values = meta.get("missing_values", []) if isinstance(meta, dict) else []
    if not isinstance(missing_values, list):
        missing_values = []
    for item in missing_values:
        if not isinstance(item, dict):
            continue
        pair = (item.get("key"), item.get("name"))
        if pair in source_pairs:
            registry.delete_value(*pair)
    _mark(name, False)
    logger.info("Откат скрипта %s: восстановлено %d ключей", name, len(files))
    return {"name": name, "restored": len(files), "returncode": 0, "state": "off"}


def _revert_command(name: str, path: Path) -> dict:
    meta = script_meta(name)
    undo = meta.get("undo")
    if not undo:
        raise RuntimeError("Для этого скрипта автоматический откат не предусмотрен")
    # Обратная команда может содержать несколько команд, разделённых символом &.
    command = undo.strip() if isinstance(undo, str) else subprocess.list2cmdline([str(part) for part in undo])
    if not command:
        raise RuntimeError("Для этого скрипта автоматический откат не предусмотрен")
    result = subprocess.run(
        [os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), "/d", "/c", command],
        capture_output=True,
        timeout=300,
        creationflags=CREATE_NO_WINDOW,
    )
    output = clean_output(decode_output((result.stdout or b"") + (result.stderr or b"")))
    if result.returncode != 0:
        raise RuntimeError(f"Откат завершился с кодом {result.returncode}: {output or 'без вывода'}")
    _mark(name, False)
    logger.info("Откат скрипта выполнен: %s", name)
    return {"name": name, "output": output or "Откат выполнен.", "returncode": 0, "state": _state_of(name, path)}


def revert_script(name: str) -> dict:
    path = resolve_script(name)
    if path.suffix.lower() == ".reg":
        return _revert_reg(name)
    return _revert_command(name, path)


def undo_from_action(name: str) -> dict:
    """Откат из общего стека «Отменить последнее действие»."""
    try:
        return revert_script(name)
    except Exception as exc:  # noqa: BLE001 - действие уже снято со стека
        raise RuntimeError(str(exc)) from exc
