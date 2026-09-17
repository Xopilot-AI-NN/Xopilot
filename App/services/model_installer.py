"""
Файл: App/services/model_installer.py
Описание: Установка официальной LiteRT-LM модели Gemma 4 E2B для Xopilot.

Скачивание потоковое: модель не держится целиком в памяти. После загрузки
проверяется SHA-256, затем временный .part атомарно заменяет целевой файл.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import urllib.request

from .llm import DEFAULT_FILENAME, MODELS_DIR


@dataclass(frozen=True)
class DownloadableModel:
    id: str
    name: str
    filename: str
    description: str
    size_label: str
    source: str
    download_url: str
    sha256: str

    @property
    def path(self) -> Path:
        return Path(MODELS_DIR) / self.filename

    @property
    def installed(self) -> bool:
        return self.path.is_file()


GEMMA_4_E2B = DownloadableModel(
    id="gemma-4-e2b",
    name="Gemma 4 E2B",
    filename=DEFAULT_FILENAME,
    description="Основная мультимодальная LiteRT-LM модель Xopilot для чата и Live.",
    size_label="~2.59 GB",
    source="litert-community/gemma-4-E2B-it-litert-lm",
    download_url=(
        "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/"
        "gemma-4-E2B-it.litertlm?download=true"
    ),
    sha256="181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c",
)

DOWNLOADABLE_MODELS = {GEMMA_4_E2B.id: GEMMA_4_E2B}


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_model(model_id: str = GEMMA_4_E2B.id) -> Path:
    """Скачать и проверить модель. Возвращает путь к установленному файлу."""
    try:
        model = DOWNLOADABLE_MODELS[model_id]
    except KeyError as exc:
        raise ValueError(f"Неизвестная модель: {model_id}") from exc

    model.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = model.path.with_name(model.path.name + ".part")
    temporary.unlink(missing_ok=True)

    request = urllib.request.Request(
        model.download_url,
        headers={"User-Agent": "Xopilot-Model-Installer/2.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(4 * 1024 * 1024):
                output.write(chunk)

        actual_hash = _digest_file(temporary)
        if actual_hash != model.sha256:
            raise RuntimeError(
                f"SHA-256 {model.name} не совпал: ожидался {model.sha256}, получен {actual_hash}."
            )
        os.replace(temporary, model.path)
        return model.path
    finally:
        temporary.unlink(missing_ok=True)
