"""
Файл: App/services/updates.py
Разработчик: DenBroLiik
Описание: Проверка опубликованного стабильного релиза Xopilot через GitHub API.
"""

import json
import re
import urllib.error
import urllib.request

VERSION = "2.0.0"
RELEASES_URL = "https://github.com/Xopilot-AI-NN/Xopilot/releases"
API_URL = "https://api.github.com/repos/Xopilot-AI-NN/Xopilot/releases/latest"


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        raise ValueError(f"Неизвестный формат версии: {value}")
    return tuple(map(int, match.groups()))


def check_updates():
    request = urllib.request.Request(API_URL, headers={
        "User-Agent": "Xopilot/" + VERSION, "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            release = json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "Стабильные релизы пока не опубликованы"
        raise RuntimeError(f"Сервер обновлений вернул HTTP {exc.code}") from exc
    latest = release["tag_name"]
    if version_tuple(latest) > version_tuple(VERSION):
        return f"Доступна версия {latest}. Скачать: {RELEASES_URL}"
    return f"Версия {VERSION} актуальна по опубликованным стабильным релизам"
