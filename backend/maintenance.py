"""Диски, SMART, TRIM и проверки целостности Windows."""
from __future__ import annotations

import os
import re
import statistics
import subprocess
import ipaddress

from . import powershell

DISK_QUERY = (
    "$disks=Get-PhysicalDisk | ForEach-Object {"
    "$r=$_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue;"
    "[pscustomobject]@{name=$_.FriendlyName; media=[string]$_.MediaType; health=[string]$_.HealthStatus;"
    "op=[string]$_.OperationalStatus; size=$_.Size; bus=[string]$_.BusType;"
    "temp=$r.Temperature; wear=$r.Wear; hours=$r.PowerOnHours}};"
    "$vols=Get-Volume | Where-Object { $_.DriveLetter } | ForEach-Object {"
    "[pscustomobject]@{letter=[string]$_.DriveLetter; label=$_.FileSystemLabel; fs=[string]$_.FileSystem;"
    "size=$_.Size; free=$_.SizeRemaining; health=[string]$_.HealthStatus}};"
    "[pscustomobject]@{disks=@($disks); volumes=@($vols)} | ConvertTo-Json -Depth 4 -Compress"
)

MEDIA_RU = {"SSD": "SSD", "HDD": "HDD", "Unspecified": "неизвестно", "SCM": "SCM"}


def disk_info() -> dict:
    data = powershell.json_object(DISK_QUERY, timeout=90)
    if not isinstance(data, dict):
        raise RuntimeError("Не удалось получить сведения о дисках через PowerShell")

    disks = data.get("disks") or []
    if isinstance(disks, dict):
        disks = [disks]
    volumes = data.get("volumes") or []
    if isinstance(volumes, dict):
        volumes = [volumes]

    prepared_disks = []
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        media = str(disk.get("media") or "Unspecified")
        prepared_disks.append(
            {
                "name": disk.get("name") or "Диск",
                "media": MEDIA_RU.get(media, media),
                "ssd": media == "SSD",
                "health": disk.get("health") or "Unknown",
                "status": disk.get("op") or "",
                "bus": disk.get("bus") or "",
                "size": int(disk.get("size") or 0),
                "temp": disk.get("temp"),
                "wear": disk.get("wear"),
                "hours": disk.get("hours"),
            }
        )

    prepared_volumes = []
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        size = int(volume.get("size") or 0)
        free = int(volume.get("free") or 0)
        prepared_volumes.append(
            {
                "letter": volume.get("letter") or "",
                "label": volume.get("label") or "",
                "fs": volume.get("fs") or "",
                "size": size,
                "free": free,
                "used_percent": round((size - free) / size * 100, 1) if size else 0,
                "health": volume.get("health") or "",
            }
        )

    prepared_disks.sort(key=lambda item: item["name"])
    prepared_volumes.sort(key=lambda item: item["letter"])
    return {"disks": prepared_disks, "volumes": prepared_volumes, "ssd_present": any(d["ssd"] for d in prepared_disks)}


def system_drive() -> str:
    return os.environ.get("SystemDrive", "C:").rstrip("\\")


def ping_host(host: str) -> dict:
    """Проверяет задержку до указанного узла четырьмя ICMP-запросами."""
    host = str(host or "").strip().rstrip(".")
    if not host or len(host) > 253 or any(char.isspace() for char in host):
        raise ValueError("Введите IP-адрес или имя сервера без пробелов")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Некорректное имя сервера") from exc
        labels = ascii_host.split(".")
        if any(
            not label or len(label) > 63
            or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise ValueError("Введите корректный IP-адрес или доменное имя")
        host = ascii_host

    result = subprocess.run(
        ["ping.exe", "-n", "4", "-w", "1200", host],
        capture_output=True,
        timeout=8,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    output = (result.stdout + result.stderr).decode("mbcs", errors="replace")
    # Windows локализует поле как time= / время=; потерянные пакеты не имеют latency.
    latency_matches = re.findall(
        r"(?:time|время)\s*([=<])\s*(\d+(?:[.,]\d+)?)\s*(?:ms|мс(?:ек)?)", output, re.I
    )
    latency_values = [
        (0.5 if comparator == "<" and float(value.replace(",", ".")) <= 1 else float(value.replace(",", ".")))
        for comparator, value in latency_matches
    ]
    sent = 4
    loss_match = re.search(r"\((\d+)%\s*(?:loss|потер)\w*\)", output, re.I)
    received = sent - round(sent * int(loss_match.group(1)) / 100) if loss_match else len(latency_values)
    return {
        "host": host,
        "sent": sent,
        "received": max(0, min(sent, received)),
        "lost": sent - max(0, min(sent, received)),
        "min_ms": min(latency_values) if latency_values else None,
        "avg_ms": round(statistics.mean(latency_values), 1) if latency_values else None,
        "max_ms": max(latency_values) if latency_values else None,
        "output": output[-3000:],
    }


def trim_args() -> list[str]:
    letter = system_drive().rstrip(":") or "C"
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        f"Optimize-Volume -DriveLetter {letter} -ReTrim -Verbose",
    ]


def scan_args(kind: str) -> list[str]:
    if kind == "sfc":
        return ["sfc.exe", "/scannow"]
    if kind == "dism":
        return ["dism.exe", "/online", "/cleanup-image", "/restorehealth"]
    raise ValueError("Неизвестная проверка")


SCAN_TITLES = {
    "sfc": "Проверка системных файлов (sfc /scannow)",
    "dism": "Восстановление образа Windows (DISM)",
}
