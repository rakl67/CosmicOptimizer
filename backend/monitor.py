"""Мониторинг CPU, RAM, GPU и температуры без внешних библиотек.

CPU/RAM/процессы читаются через ctypes (дёшево), GPU и температура —
через PowerShell в фоновом потоке, поэтому интерфейс никогда не ждёт.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

from .config import logger
from . import powershell

CPU_INTERVAL = 1.5
GPU_INTERVAL = 30.0
ACTIVE_GRACE_SECONDS = 5.0

GPU_PROBE = (
    "$gpu=(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | "
    "Measure-Object -Property UtilizationPercentage -Sum).Sum;"
    "$vc=Get-CimInstance Win32_VideoController | Where-Object { $_.Status -eq 'OK' } | Select-Object -First 1;"
    "$tz=Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue;"
    "$t=$null; if($tz){$t=[math]::Round((($tz|Measure-Object -Property CurrentTemperature -Maximum).Maximum/10)-273.15,0)};"
    "$ram=(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty AdapterRAM);"
    "[pscustomobject]@{gpu=[math]::Round([double]$gpu,0); temp=$t; name=$vc.Name; "
    "vram=[math]::Round([double]$ram/1GB,1)} | ConvertTo-Json -Compress"
)


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _ft(value: _FILETIME) -> int:
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def _cpu_times() -> tuple[int, int, int] | None:
    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        return None
    return _ft(idle), _ft(kernel), _ft(user)


def _memory() -> dict:
    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"ram_percent": None, "ram_total_mb": None, "ram_used_mb": None}
    total = status.ullTotalPhys / 1048576
    used = (status.ullTotalPhys - status.ullAvailPhys) / 1048576
    return {
        "ram_percent": round(status.dwMemoryLoad, 0),
        "ram_total_mb": round(total),
        "ram_used_mb": round(used),
    }


def _process_count() -> int | None:
    array = (wintypes.DWORD * 4096)()
    needed = wintypes.DWORD()
    ok = ctypes.windll.psapi.EnumProcesses(ctypes.byref(array), ctypes.sizeof(array), ctypes.byref(needed))
    if not ok:
        return None
    count = needed.value // ctypes.sizeof(wintypes.DWORD)
    return sum(1 for index in range(count) if array[index])


def _uptime() -> int:
    return int(ctypes.windll.kernel32.GetTickCount64() / 1000)


class Monitor:
    """Фоновый сэмплер: интерфейс всегда получает готовый снимок мгновенно."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._data = {
            "cpu": None,
            "ram_percent": None,
            "ram_total_mb": None,
            "ram_used_mb": None,
            "gpu": None,
            "temp": None,
            "gpu_name": None,
            "vram_gb": None,
            "processes": None,
            "uptime": 0,
            "cores": os.cpu_count() or 0,
            "gpu_supported": True,
        }
        self._prev = _cpu_times()
        self._active_until = 0.0

    def _start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="monitor")
        self._thread.start()

    def _loop(self) -> None:
        last_gpu = 0.0
        while True:
            if time.monotonic() > self._active_until:
                time.sleep(1.0)
                continue
            try:
                now = _cpu_times()
                cpu = None
                if now and self._prev:
                    idle = now[0] - self._prev[0]
                    total = (now[1] - self._prev[1]) + (now[2] - self._prev[2])
                    if total > 0:
                        cpu = max(0.0, min(100.0, 100.0 * (1 - idle / total)))
                if now:
                    self._prev = now

                memory = _memory()
                with self._lock:
                    self._data.update(memory)
                    self._data["cpu"] = round(cpu, 1) if cpu is not None else None
                    self._data["processes"] = _process_count()
                    self._data["uptime"] = _uptime()

                if time.monotonic() - last_gpu >= GPU_INTERVAL:
                    last_gpu = time.monotonic()
                    self._probe_gpu()
            except Exception as exc:  # noqa: BLE001 - сэмплер не должен умирать
                logger.warning("Мониторинг: %s", exc)
            time.sleep(CPU_INTERVAL)

    def _probe_gpu(self) -> None:
        try:
            data = powershell.json_object(GPU_PROBE, timeout=25)
        except Exception as exc:  # noqa: BLE001 - GPU-счётчики есть не всегда
            logger.debug("GPU-опрос недоступен: %s", exc)
            with self._lock:
                self._data["gpu_supported"] = False
            return
        if not isinstance(data, dict):
            with self._lock:
                self._data["gpu_supported"] = False
            return
        gpu = data.get("gpu")
        try:
            gpu = min(100.0, max(0.0, float(gpu))) if gpu is not None else None
        except (TypeError, ValueError):
            gpu = None
        temp = data.get("temp")
        try:
            temp = float(temp) if temp is not None else None
        except (TypeError, ValueError):
            temp = None
        with self._lock:
            self._data["gpu"] = round(gpu, 1) if gpu is not None else None
            self._data["temp"] = round(temp, 1) if temp is not None else None
            self._data["gpu_name"] = data.get("name")
            self._data["vram_gb"] = data.get("vram")
            self._data["gpu_supported"] = True

    def metrics(self) -> dict:
        # Не оставляем сэмплер крутиться после остановки опроса интерфейсом.
        self._active_until = time.monotonic() + ACTIVE_GRACE_SECONDS
        self._start()
        with self._lock:
            empty = self._data["ram_total_mb"] is None
        if empty:
            # первый вызов: сразу отдаём дешёвые показатели, не дожидаясь потока
            try:
                with self._lock:
                    self._data.update(_memory())
                    self._data["processes"] = _process_count()
                    self._data["uptime"] = _uptime()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Первый снимок: %s", exc)
        with self._lock:
            payload = dict(self._data)
        payload["threads"] = None
        return payload


_monitor = Monitor()


def metrics() -> dict:
    return _monitor.metrics()
