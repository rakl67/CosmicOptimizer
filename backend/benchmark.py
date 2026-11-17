"""Bounded storage assessment through the Windows System Assessment Tool."""
from __future__ import annotations

import re
import subprocess
import time

from . import jobs

CREATE_NO_WINDOW = 0x08000000
_RATE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*(?:MB/s|МБ/с|МБ\s*/\s*с)", re.IGNORECASE)


def run(duration: int, drive: str, job: dict) -> dict:
    """Runs four standard sequential/random read/write tests, capped by duration."""
    duration = int(duration)
    if duration < 10 or duration > 60:
        raise ValueError("Длительность теста должна быть от 10 до 60 секунд")
    drive = str(drive or "").strip().upper().rstrip(":\\")
    if len(drive) != 1 or not drive.isalpha():
        raise ValueError("Выберите доступный диск")
    tests = [("seq_read", "-seq", "-read", "Последовательное чтение"),
             ("seq_write", "-seq", "-write", "Последовательная запись"),
             ("random_read", "-ran", "-read", "Случайное чтение"),
             ("random_write", "-ran", "-write", "Случайная запись")]
    started = time.monotonic()
    results = {}
    for index, (key, pattern, direction, label) in enumerate(tests, 1):
        remaining = duration - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Лимит времени теста исчерпан; запустите более длительный прогон")
        jobs.update_progress(job, (index - 1) * 25, label)
        # Единые параметры делают повторные запуски сопоставимыми.
        # На каждый этап ограничиваем нагрузку 512 операциями.
        block = "-seqsize" if pattern == "-seq" else "-ransize"
        block_size = "1048576" if pattern == "-seq" else "16384"
        command = ["winsat.exe", "disk", pattern, direction, "-drive", drive,
                   "-count", "1", "-iocount", "512", block, block_size, "-v"]
        try:
            proc = subprocess.run(command, capture_output=True, timeout=max(1, remaining), creationflags=CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Тест «{label}» остановлен по лимиту {duration} секунд") from exc
        output = (proc.stdout or b"").decode("mbcs", errors="replace") + "\n" + (proc.stderr or b"").decode("mbcs", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"WinSAT не выполнил тест «{label}»: {output[-600:].strip() or f'код {proc.returncode}'}")
        values = _RATE.findall(output)
        if not values:
            raise RuntimeError(f"WinSAT завершил «{label}», но не вернул скорость. Проверьте, что тест поддерживается Windows.")
        results[key] = float(values[-1].replace(",", "."))
        jobs.update_progress(job, index * 25, f"Готово: {label}")
    elapsed = time.monotonic() - started
    return {
        **results,
        "duration_seconds": round(elapsed, 1),
        "drive": f"{drive}:",
        "method": "WinSAT · 1 МиБ последовательные блоки, 16 КиБ случайные блоки, 512 операций на режим. Сравнивайте прогоны на одном ПК при одинаковых условиях.",
    }
