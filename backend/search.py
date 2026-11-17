"""Умный поиск по твикам, скриптам, инструментам и разделам.

Понимает опечатки, часть слова и текст, набранный в неправильной раскладке
(«rjvyfylf» найдёт «команда»).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from time import monotonic

from . import scripts, tools
from .tweaks_catalog import CATEGORIES, TWEAKS

LAYOUT = dict(
    zip(
        "qwertyuiop[]asdfghjkl;'zxcvbnm,./",
        "йцукенгшщзхъфывапролджэячсмитьбю.",
    )
)
CLEAN_RE = re.compile(r"[^0-9a-zа-яё]+")
# «Встроено в «Реестр → Игры»», «в разделе «Реестр»» — перекрёстная ссылка, а не суть.
XREF_RE = re.compile(r"(?:встроено в|в разделе)\s*[«\"].*?[»\"]")
QUOTE_RE = re.compile(r"«[^»]*(?:→|реестр)[^»]*»")

VIEWS = [
    {"id": "dashboard", "title": "Обзор", "subtitle": "Мониторинг, бэкап и журнал"},
    {"id": "registry", "title": "Реестр", "subtitle": "25 твиков по категориям"},
    {"id": "devices", "title": "Видеокарта и устройства", "subtitle": "Включение и отключение PnP"},
    {"id": "maintenance", "title": "Обслуживание", "subtitle": "Мастер диагностики, очистка, диски и проверки"},
    {"id": "scripts", "title": "Мои скрипты", "subtitle": "Материалы из исходной папки"},
    {"id": "tools", "title": "Инструменты", "subtitle": "BoosterX, Process Lasso, MSI, Debloat"},
    {"id": "backups", "title": "Бэкапы", "subtitle": "Точки отката и переносимый профиль настроек"},
    {"id": "logs", "title": "Логи", "subtitle": "Журнал действий"},
    {"id": "settings", "title": "Настройки", "subtitle": "Подтверждения и данные"},
]

# Подразделы обслуживания — чтобы «очистка мусора» находилась поиском.
MAINTENANCE_ITEMS = [
    {"title": "Мастер диагностики", "subtitle": "Пошаговые проверки: загрузка, микрофризы, ping, температура, диск и ошибки Windows"},
    {"title": "Очистка мусора", "subtitle": "Temp, кэши, корзина, Windows.old, DISM"},
    {"title": "Диски, SMART и TRIM", "subtitle": "Здоровье дисков и свободное место"},
    {"title": "Проверка целостности Windows", "subtitle": "sfc /scannow и DISM RestoreHealth"},
    {"title": "Замер «до и после»", "subtitle": "Процессы, ОЗУ и время загрузки"},
    {"title": "Профиль настроек для другого компьютера", "subtitle": "Экспорт и импорт одного файла с фильтром настроек под видеокарту", "view": "backups"},
]

DASHBOARD_ITEMS = [
    {"title": "Мониторинг в реальном времени", "subtitle": "CPU, RAM, GPU и температура"},
    {"title": "Глобальный поиск", "subtitle": "Ctrl+K по твикам, скриптам и инструментам"},
]


def _norm(text: str) -> str:
    lowered = (text or "").lower().replace("ё", "е")
    lowered = QUOTE_RE.sub(" ", XREF_RE.sub(" ", lowered))
    return CLEAN_RE.sub(" ", lowered).strip()


def _to_layout(text: str) -> str:
    result = []
    for char in text.lower():
        if char in LAYOUT:
            result.append(LAYOUT[char])
        elif char in LAYOUT.values():
            result.append(next(key for key, value in LAYOUT.items() if value == char))
        else:
            result.append(char)
    return "".join(result)


def _token_score(token: str, words: list[str]) -> float:
    """Лучшее совпадение токена со словом: точное, по началу и с опечатками."""
    best = 0.0
    for word in words:
        if word.startswith(token) or (len(token) >= 4 and token in word):
            return 1.0
        if abs(len(word) - len(token)) <= 3:
            ratio = SequenceMatcher(None, token, word).ratio()
            if ratio > best:
                best = ratio
    return best


# Поля идут по важности: название, описание, имя файла / значение, категория.
FIELD_WEIGHTS = (1.0, 0.75, 0.6, 0.55)


def _score(query: str, fields: list[str], prepared: bool = False) -> float:
    if not query:
        return 0.0
    best = 0.0
    tokens = [token for token in query.split() if token]
    for index, field in enumerate(fields):
        text = field if prepared else _norm(field)
        if not text:
            continue
        field_best = 0.0
        if text == query:
            field_best = 100.0
        elif text.startswith(query):
            field_best = 90.0
        elif query in text:
            field_best = 78.0

        words = text.split()
        ratios = [_token_score(token, words) for token in tokens]
        strong = len(ratios) > 1 and min(ratios) >= 0.99
        if strong:
            # все слова запроса есть в тексте — это не случайное совпадение
            field_best = 100.0
        elif ratios and max(ratios) >= 0.72:
            field_best = max(field_best, 50.0 + 50.0 * (sum(ratios) / len(ratios)))

        # опечатка в коротком заголовке целиком
        if len(text) <= 40:
            ratio = SequenceMatcher(None, query, text).ratio()
            if ratio > 0.66:
                field_best = max(field_best, 40.0 + 45.0 * ratio)

        weight = 1.0 if strong else FIELD_WEIGHTS[min(index, len(FIELD_WEIGHTS) - 1)]
        best = max(best, field_best * weight)
    return best


def _variants(query: str) -> list[str]:
    base = _norm(query)
    if not base:
        return []
    variants = {base}
    converted = _norm(_to_layout(query))
    if converted:
        variants.add(converted)
    # каждое слово тоже может быть набрано в другой раскладке
    if len(base.split()) > 1:
        variants.add(" ".join(_to_layout(part) for part in base.split()))
    return [item for item in variants if item]


_catalog_cache: tuple[float, list[dict]] | None = None
CATALOG_TTL = 120.0


def _catalog() -> list[dict]:
    """Каталог кэшируется: иначе каждый символ в поиске заново читал бы реестр скриптов."""
    global _catalog_cache
    now = monotonic()
    if _catalog_cache and now - _catalog_cache[0] < CATALOG_TTL:
        return _catalog_cache[1]
    items = _build_catalog()
    _catalog_cache = (now, items)
    return items


def _build_catalog() -> list[dict]:
    items: list[dict] = []
    categories = {item["id"]: item["name"] for item in CATEGORIES}
    for view in VIEWS:
        items.append(
            {
                "type": "view",
                "id": view["id"],
                "title": view["title"],
                "subtitle": view["subtitle"],
                "view": view["id"],
                "fields": [view["title"], view["subtitle"]],
            }
        )
    for index, area in enumerate(DASHBOARD_ITEMS + MAINTENANCE_ITEMS):
        items.append(
            {
                "type": "view",
                "id": f"area-{index}",
                "title": area["title"],
                "subtitle": area["subtitle"],
                "view": area.get("view", "maintenance"),
                "fields": [area["title"], area["subtitle"], "обслуживание"],
            }
        )
    for tweak in TWEAKS:
        items.append(
            {
                "type": "tweak",
                "id": tweak["id"],
                "title": tweak["name"],
                "subtitle": f"{categories.get(tweak['category'], tweak['category'])} · {tweak['description'][:110]}",
                "view": "registry",
                "category": tweak["category"],
                "fields": [tweak["name"], tweak["description"], tweak["value_name"], categories.get(tweak["category"], "")],
            }
        )
    try:
        for script in scripts.list_scripts():
            items.append(
                {
                    "type": "script",
                    "id": script["name"],
                    "title": script["title"],
                    "subtitle": f"{script['group']} · {script['name']}",
                    "view": "scripts",
                    "query": script["title"],
                    "fields": [script["title"], script["description"], script["name"], script["group"]],
                }
            )
    except Exception:  # noqa: BLE001 - поиск не должен падать из-за скриптов
        pass
    for tool in tools.tools_catalog():
        items.append(
            {
                "type": "tool",
                "id": tool["id"],
                "title": tool["title"],
                "subtitle": tool["tagline"],
                "view": "tools",
                "fields": [tool["title"], tool["tagline"], tool["description"]],
            }
        )
    # нормализуем поля один раз: поиск идёт на каждый символ ввода
    for item in items:
        item["norm"] = [_norm(field) for field in item["fields"]]
    return items


def search(query: str, limit: int = 30) -> list[dict]:
    variants = _variants(query)
    if not variants:
        return []
    results = []
    for item in _catalog():
        fields = item.get("norm") or item["fields"]
        score = max(_score(variant, fields, prepared=True) for variant in variants)
        if score >= 65:
            results.append((score, item))
    results.sort(key=lambda pair: (-pair[0], pair[1]["title"]))
    payload = []
    for score, item in results[:limit]:
        payload.append(
            {
                "type": item["type"],
                "id": item["id"],
                "title": item["title"],
                "subtitle": item["subtitle"],
                "view": item["view"],
                "category": item.get("category"),
                "query": item.get("query"),
                "score": round(score),
            }
        )
    return payload
