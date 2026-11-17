"""Пути, настройки и логирование Cosmic Optimizer."""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "Cosmic Optimizer"
APP_DIR_NAME = "CosmicOptimizer"
VERSION = "1.0.0"
AUTHOR = "rakl679"

FROZEN = bool(getattr(sys, "frozen", False))
# В собранном виде всё внутри .exe (_MEIPASS), внешних папок не создаётся.
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "ui"
SCRIPTS_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "scripts"
# onefile: скрипты встроены в .exe, читаются напрямую из _MEIPASS (только для чтения).
BUNDLED_SCRIPTS = SCRIPTS_DIR


def prepare_scripts() -> None:
    """Для onefile: скрипты уже внутри .exe, внешнюю папку не создаём."""
    return

DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_DIR_NAME
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"
SETTINGS_FILE = DATA_DIR / "settings.json"
ACTIONS_FILE = DATA_DIR / "actions.json"
LOG_FILE = LOGS_DIR / "app.log"

DEFAULT_SETTINGS = {
    "confirmations": True,
    "auto_backup": True,
    "profile_restore_point": None,
    "backups_dir": str(BACKUPS_DIR),
    "onboarding_done": False,
}

logger = logging.getLogger("cosmic")


def ensure_dirs() -> None:
    for path in (DATA_DIR, BACKUPS_DIR, LOGS_DIR):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


def setup_logging() -> logging.Logger:
    ensure_dirs()
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
        try:
            handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
            handler.setFormatter(fmt)
            logger.addHandler(handler)
        except OSError:
            pass
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        logger.addHandler(stream)
    return logger


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Не удалось прочитать настройки: %s", exc)
    settings["auto_backup"] = bool(settings.get("auto_backup", True))
    settings["confirmations"] = bool(settings.get("confirmations", True))
    if not isinstance(settings.get("profile_restore_point"), bool):
        settings["profile_restore_point"] = None
    settings["onboarding_done"] = bool(settings.get("onboarding_done", False))
    if not settings.get("backups_dir"):
        settings["backups_dir"] = str(BACKUPS_DIR)
    return settings


def save_settings(settings: dict) -> dict:
    ensure_dirs()
    current = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in settings:
            current[key] = settings[key]
    current["auto_backup"] = bool(current.get("auto_backup", True))
    current["confirmations"] = bool(current.get("confirmations", True))
    current["onboarding_done"] = bool(current.get("onboarding_done", False))
    SETTINGS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def backups_dir() -> Path:
    path = Path(load_settings().get("backups_dir") or BACKUPS_DIR)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = BACKUPS_DIR
        path.mkdir(parents=True, exist_ok=True)
    return path


def clear_log() -> None:
    """Обнуляет текущий файл лога, не теряя открытый обработчик."""
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.acquire()
            try:
                handler.stream.seek(0)
                handler.stream.truncate(0)
            finally:
                handler.release()
    try:
        LOG_FILE.write_text("", encoding="utf-8")
    except OSError:
        pass
