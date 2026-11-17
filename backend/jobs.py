"""Фоновые задачи: долгие команды без блокировки интерфейса."""
from __future__ import annotations

import codecs
import itertools
import re
import subprocess
import threading
import time
from datetime import datetime

from .config import logger
from .powershell import CREATE_NO_WINDOW

MAX_LINES = 400
JOBS: dict[str, dict] = {}
_lock = threading.Lock()
_counter = itertools.count(1)
_PERCENT = re.compile(r"(?<!\d)(\d{1,3})(?:[.,]\d+)?\s*%")


def _create(title: str, command: str = "") -> dict:
    job = {
        "id": f"job{next(_counter)}",
        "title": title,
        "command": command,
        "status": "running",
        "progress_percent": None,
        "progress_message": "Подготовка…",
        "output": [],
        "result": None,
        "error": None,
        "started": datetime.now().isoformat(timespec="seconds"),
        "finished": None,
        "started_monotonic": time.monotonic(),
    }
    with _lock:
        JOBS[job["id"]] = job
    return job


def _append(job: dict, text: str) -> None:
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.rstrip()
        if not line:
            continue
        with _lock:
            job["output"].append(line)
            if len(job["output"]) > MAX_LINES:
                del job["output"][: len(job["output"]) - MAX_LINES]
            job["progress_message"] = line[:240]
        match = _PERCENT.search(line)
        if match:
            update_progress(job, min(100, int(match.group(1))), line[:240])


def update_progress(job: dict, percent: float | None, message: str = "") -> None:
    """Обновляет ход задачи; None оставляет процент неизвестным и включает анимацию ожидания."""
    if percent is not None:
        percent = max(0, min(100, float(percent)))
    with _lock:
        job["progress_percent"] = percent
        if message:
            job["progress_message"] = str(message)[:240]


def _finish(job: dict, status: str, result=None, error: str | None = None) -> None:
    with _lock:
        job["status"] = status
        job["result"] = result
        job["error"] = error
        job["finished"] = datetime.now().isoformat(timespec="seconds")
        if status == "done":
            job["progress_percent"] = 100
            job["progress_message"] = "Готово"
        elif error:
            job["progress_message"] = str(error)[:240]


def start_process(title: str, args: list[str], timeout: int = 5400) -> dict:
    """Запускает процесс и построчно копит вывод (возвращает задачу сразу)."""
    job = _create(title, subprocess.list2cmdline(args))
    logger.info("Задача %s: %s", job["id"], title)

    def worker() -> None:
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            _finish(job, "error", error=f"Не удалось запустить: {exc}")
            return

        decoder = codecs.getincrementaldecoder("cp866")(errors="replace")
        buffer = ""
        deadline = time.monotonic() + timeout
        assert process.stdout is not None
        try:
            while True:
                chunk = process.stdout.read(2048)
                if not chunk:
                    break
                buffer += decoder.decode(chunk)
                parts = buffer.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                buffer = parts.pop()
                if parts:
                    _append(job, "\n".join(parts))
                if time.monotonic() > deadline:
                    process.kill()
                    _finish(job, "error", error=f"Превышен лимит {timeout // 60} минут — процесс остановлен")
                    return
            tail = buffer + decoder.decode(b"", final=True)
            if tail.strip():
                _append(job, tail)
            code = process.wait()
        except OSError as exc:
            _finish(job, "error", error=f"Ошибка чтения вывода: {exc}")
            return

        if code == 0:
            _finish(job, "done", result={"returncode": 0})
            logger.info("Задача %s завершена успешно", job["id"])
        else:
            _finish(job, "error", result={"returncode": code}, error=f"Команда завершилась с кодом {code}")
            logger.warning("Задача %s: код %s", job["id"], code)

    threading.Thread(target=worker, daemon=True, name=f"job-{job['id']}").start()
    return job


def start_task(title: str, func) -> dict:
    """Запускает Python-функцию в фоне; результат — её возвращаемое значение."""
    job = _create(title)
    logger.info("Задача %s: %s", job["id"], title)

    def worker() -> None:
        try:
            result = func(job)
            _finish(job, "done", result=result)
            logger.info("Задача %s завершена", job["id"])
        except Exception as exc:  # noqa: BLE001 - фоновая задача
            logger.exception("Задача %s упала", job["id"])
            _finish(job, "error", error=str(exc).strip() or exc.__class__.__name__)

    threading.Thread(target=worker, daemon=True, name=f"job-{job['id']}").start()
    return job


def status(job_id: str) -> dict:
    with _lock:
        job = JOBS.get(job_id)
        if job is None:
            raise ValueError("Задача не найдена или уже закрыта")
        payload = dict(job)
        payload["output"] = list(job["output"])
    payload["elapsed"] = round(time.monotonic() - job["started_monotonic"], 1)
    payload.pop("started_monotonic", None)
    return payload


def cleanup_old(max_age_seconds: int = 3600) -> None:
    """Убирает из памяти завершённые задачи старше часа."""
    now = time.monotonic()
    with _lock:
        for key in [
            key
            for key, job in JOBS.items()
            if job["status"] != "running" and now - job["started_monotonic"] > max_age_seconds
        ]:
            JOBS.pop(key, None)
