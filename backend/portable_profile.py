"""Экспорт и импорт переносимых состояний твиков Cosmic Optimizer."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import backup, devices, registry
from .config import VERSION, logger
from .tweaks_catalog import TWEAKS, TWEAKS_BY_ID

FORMAT = "cosmic-optimizer-profile"
SCHEMA_VERSION = 1
MAX_PROFILE_BYTES = 1024 * 1024
MAX_TWEAKS = 100

# Эти записи относятся к драйверу конкретного семейства GPU.
GPU_REQUIREMENTS = {
    "amd_ulps_off": {"amd"},
    "gpu_per_core_dpc": {"amd", "nvidia"},
}
VENDOR_NAMES = {"amd": "AMD", "nvidia": "NVIDIA", "intel": "Intel"}
GPU_TWEAK_IDS = {tweak["id"] for tweak in TWEAKS if tweak.get("category") == "graphics"}


def _vendor_set(vendors) -> set[str]:
    return {str(v).lower() for v in (vendors or []) if str(v).lower() in {"amd", "nvidia", "intel"}}


def _supports_vendor(tweak_id: str, vendors: set[str]) -> bool:
    required = GPU_REQUIREMENTS.get(tweak_id)
    # GPU-каталог закрыт по умолчанию: новый графический твик надо явно
    # привязать к поддерживаемому семейству, иначе перенос его не применит.
    if tweak_id in GPU_TWEAK_IDS and required is None:
        return False
    return required is None or bool(required & vendors)


def detect_gpu_vendors() -> list[str]:
    """Определяет производителей только по физически присутствующим PnP-видеокартам."""
    vendors = set()
    for device in devices.list_devices():
        name = str(device.get("name") or "").upper()
        instance = str(device.get("instance_id") or "").upper()
        if "VEN_1002" in instance or "AMD" in name or "RADEON" in name:
            vendors.add("amd")
        if "VEN_10DE" in instance or "NVIDIA" in name:
            vendors.add("nvidia")
        if "VEN_8086" in instance or "INTEL" in name:
            vendors.add("intel")
    return sorted(vendors)


def export_profile(target: Path, vendors) -> dict:
    """Сохраняет состояния известных твиков в один безопасный JSON-файл."""
    vendors = _vendor_set(vendors)
    states = {}
    skipped_gpu = []
    for tweak in TWEAKS:
        state = registry.get_state(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"])
        if state not in {"on", "off"}:
            continue
        if not _supports_vendor(tweak["id"], vendors):
            skipped_gpu.append(tweak["id"])
            continue
        states[tweak["id"]] = state

    document = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "app_version": VERSION,
        "gpu_vendors": sorted(vendors),
        "tweak_states": states,
    }
    target = Path(target)
    if target.suffix.lower() != ".cosmicprofile":
        target = target.with_suffix(".cosmicprofile")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Профиль экспортирован: %s (твиков: %d, пропущено GPU: %d)", target.name, len(states), len(skipped_gpu))
    return {"path": str(target), "filename": target.name, "count": len(states), "skipped_gpu": len(skipped_gpu)}


def read_profile(path: Path, local_vendors) -> dict:
    """Проверяет переносимый профиль и готовит список допустимых твиков к показу."""
    path = Path(path)
    size = path.stat().st_size
    if size <= 0 or size > MAX_PROFILE_BYTES:
        raise ValueError("Размер файла профиля недопустим (максимум 1 МБ)")
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Файл не является корректным профилем Cosmic Optimizer") from exc
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise ValueError("Это не профиль Cosmic Optimizer")
    if type(document.get("schema_version")) is not int or document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Версия формата профиля не поддерживается этой версией приложения")
    states = document.get("tweak_states")
    if not isinstance(states, dict) or len(states) > MAX_TWEAKS:
        raise ValueError("В профиле некорректный список настроек")
    if any(
        not isinstance(tweak_id, str) or len(tweak_id) > 100
        or not isinstance(state, str) or state not in {"on", "off"}
        for tweak_id, state in states.items()
    ):
        raise ValueError("В профиле есть некорректное состояние настройки")

    local_vendors = _vendor_set(local_vendors)
    applicable, incompatible, unknown, unavailable = [], [], [], []
    for tweak_id, desired_state in states.items():
        tweak = TWEAKS_BY_ID.get(tweak_id)
        if tweak is None:
            unknown.append(tweak_id)
            continue
        if not _supports_vendor(tweak_id, local_vendors):
            required = GPU_REQUIREMENTS.get(tweak_id, set())
            if required and not local_vendors:
                reason = "на этом ПК видеокарта не обнаружена"
            elif required:
                reason = "нужна видеокарта " + " или ".join(VENDOR_NAMES[v] for v in sorted(required))
            elif tweak_id in GPU_TWEAK_IDS:
                reason = "семейство видеокарты не подтверждено приложением"
            else:
                reason = "нет поддерживаемой видеокарты"
            incompatible.append(f"{tweak['name']} — пропущено: {reason}")
            continue
        if not registry.key_exists(tweak["key_path"]):
            unavailable.append(tweak["name"])
            continue
        applicable.append({
            "id": tweak_id,
            "name": tweak["name"],
            "restart": tweak["restart"],
            "state": desired_state,
            "current_state": registry.get_state(tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"]),
        })

    source_vendors = _vendor_set(document.get("gpu_vendors"))
    return {
        "profile": document,
        "created": str(document.get("created") or ""),
        "app_version": str(document.get("app_version") or ""),
        "source_vendors": sorted(source_vendors),
        "local_vendors": sorted(local_vendors),
        "applicable": applicable,
        "incompatible": incompatible,
        "unknown": unknown,
        "unavailable": unavailable,
    }


def apply_profile(preview: dict, job: dict | None = None) -> dict:
    """Создаёт полный локальный бэкап и применяет только предварительно разрешённые состояния."""
    profile = preview.get("profile")
    if not isinstance(profile, dict) or profile.get("format") != FORMAT:
        raise ValueError("Нет проверенного профиля для импорта")
    profile_states = profile.get("tweak_states")
    local_vendors = _vendor_set(preview.get("local_vendors"))
    applicable = [
        item for item in preview.get("applicable", [])
        if isinstance(item, dict)
        and item.get("id") in TWEAKS_BY_ID
        and item.get("state") == profile_states.get(item.get("id"))
        and item.get("state") in {"on", "off"}
        and _supports_vendor(item["id"], local_vendors)
    ] if isinstance(profile_states, dict) else []
    if not applicable:
        raise ValueError("В профиле нет совместимых с этим ПК настроек")

    from . import jobs
    progress = (lambda percent, message: jobs.update_progress(job, percent, message)) if job is not None else None
    if progress:
        progress(0, "Создание защитного бэкапа перед импортом…")
    snapshot = backup.create_backup(
        note="Перед импортом переносимого профиля",
        progress=(lambda percent, message: progress(percent * 0.35, f"Бэкап · {message}")) if progress else None,
    )
    if snapshot.get("failed"):
        details = "; ".join(snapshot["failed"][:3])
        raise RuntimeError(f"Импорт отменён: не удалось полностью сохранить текущий реестр. {details}")

    applied, unchanged, failed = [], [], []
    for index, item in enumerate(applicable, 1):
        tweak_id = item["id"]
        tweak = TWEAKS_BY_ID[tweak_id]
        desired_state = item["state"]
        if progress:
            progress(35 + index * 65 / len(applicable), f"Применение настройки {index} из {len(applicable)}: {tweak['name']}")
        try:
            current_state = registry.get_state(
                tweak["key_path"], tweak["value_name"], tweak["on_value"], tweak["off_value"]
            )
            if current_state == "missing":
                failed.append({"name": tweak["name"], "error": "Параметр не поддерживается этой системой"})
                continue
            if current_state == desired_state:
                unchanged.append(tweak["name"])
                continue
            prev_exists, prev_value, _ = registry.read_value(tweak["key_path"], tweak["value_name"])
            desired_value = tweak["on_value"] if desired_state == "on" else tweak["off_value"]
            registry.write_value(tweak["key_path"], tweak["value_name"], desired_value, tweak["value_type"])
            backup.record_action(
                {
                    "type": "tweak",
                    "id": tweak_id,
                    "name": tweak["name"],
                    "prev_exists": prev_exists,
                    "prev_value": prev_value,
                    "profile_import": True,
                }
            )
            applied.append({"name": tweak["name"], "state": desired_state, "restart": tweak["restart"]})
        except Exception as exc:  # noqa: BLE001 - остальные настройки профиля обрабатываются независимо
            failed.append({"name": tweak["name"], "error": str(exc)})

    logger.info("Импорт профиля: изменено %d, без изменений %d, ошибок %d", len(applied), len(unchanged), len(failed))
    return {
        "applied": applied,
        "unchanged": unchanged,
        "failed": failed,
        "backup": snapshot["name"],
    }
