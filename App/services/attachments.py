"""
Файл: App/services/attachments.py
Описание: Разбор вложений (файлы, прикреплённые к сообщению) для передачи в мультимодальную модель.
    Изображения -> сжимаются (Pillow) и идёт модели как картинка (Content.ImageBytes в llm.py).
    Текстовые/код файлы, PDF (pypdf), DOCX (python-docx) -> читаются в текст и добавляется к промпту.
    Видео -> несколько равномерно распределённых кадров через OpenCV, тоже как картинки.
    Неизвестные форматы или отсутствующие библиотеки -> короткая пометка в тексте, без падения.

    Главная функция — build_attachment_message_parts(). Никогда не бросает исключение:
    ошибка чтения одного файла не должна обрывать отправку сообщения из-за других вложений.
"""

import io
import os

try:
    from PIL import Image
except Exception:
    Image = None
try:
    import cv2
except Exception:
    cv2 = None
try:
    import pypdf
except Exception:
    pypdf = None
try:
    import docx
except Exception:
    docx = None

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".csv",
    ".log", ".yaml", ".yml", ".html", ".htm", ".css", ".xml", ".rs", ".toml", ".ini",
    ".sh", ".bash", ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rb", ".sql", ".cfg",
}

MAX_TEXT_CHARS = 20000
MAX_IMAGE_SIDE = 1024
VIDEO_FRAME_COUNT = 3


def _downscale_image_bytes(raw: bytes) -> bytes:
    """Уменьшает и перекодирует в JPEG — без этого большие фото медленно идут через FFI-мостик
    и упираются в бюджет визуальных токенов модели (max_vision_token_budget). При отсутствии Pillow
    возвращает исходные байты как есть — модель всё равно попробует принять исходный формат.
    """
    if Image is None:
        return raw
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=87)
            return out.getvalue()
    except Exception:
        return raw


def _read_text_file(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read(MAX_TEXT_CHARS * 4)
    text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n…[обрезано]"
    return text


def _read_pdf(path: str) -> str:
    if pypdf is None:
        return "[PDF: для чтения нужен pypdf — не установлен]"
    try:
        reader = pypdf.PdfReader(path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as exc:
        return f"[Не удалось прочитать PDF: {exc}]"
    if not text:
        return "[PDF без извлекаемого текста — возможно, это скан]"
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n…[обрезано]"
    return text


def _read_docx(path: str) -> str:
    if docx is None:
        return "[DOCX: для чтения нужен python-docx — не установлен]"
    try:
        document = docx.Document(path)
        text = "\n".join(p.text for p in document.paragraphs).strip()
    except Exception as exc:
        return f"[Не удалось прочитать DOCX: {exc}]"
    if not text:
        return "[DOCX без текста]"
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n…[обрезано]"
    return text


def _extract_video_frames(path: str, count: int = VIDEO_FRAME_COUNT) -> list[bytes]:
    """Равномерно распределённые кадры видео как JPEG-байты (litert_lm не имеет отдельного
    типа для видеофайлов — только для живого видео-модальности, которую текущая модель не поддерживает).
    """
    if cv2 is None:
        return []
    cap = cv2.VideoCapture(path)
    frames: list[bytes] = []
    try:
        if not cap.isOpened():
            return frames
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        positions = (
            [int(total * (i + 1) / (count + 1)) for i in range(count)]
            if total > 0
            else [0]
        )
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                continue
            ok2, buf = cv2.imencode(".jpg", frame)
            if ok2:
                frames.append(buf.tobytes())
    finally:
        cap.release()
    return frames


def build_attachment_message_parts(attachments):
    """attachments: [(имя, путь), ...].

    Возвращает (text_notes: list[str], images: list[bytes]):
      - text_notes добавляются к тексту промпта (содержимое текстовых/PDF/DOCX файлов,
        пометки о нечитаемых файлах);
      - images передаются модели как Content.ImageBytes (фото и кадры видео).
    """
    text_notes: list[str] = []
    images: list[bytes] = []
    for name, path in attachments:
        if not path or not os.path.isfile(path):
            text_notes.append(f"[Файл «{name}» недоступен на диске]")
            continue
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in IMAGE_EXTENSIONS:
                with open(path, "rb") as f:
                    raw = f.read()
                images.append(_downscale_image_bytes(raw))
            elif ext in VIDEO_EXTENSIONS:
                frames = _extract_video_frames(path)
                if frames:
                    text_notes.append(f"[Ниже — {len(frames)} кадр(ов) из видео «{name}»]")
                    images.extend(frames)
                else:
                    text_notes.append(f"[Не удалось извлечь кадры из видео «{name}» — нужен opencv-python]")
            elif ext == ".pdf":
                text_notes.append(f"--- Файл «{name}» (PDF) ---\n{_read_pdf(path)}")
            elif ext == ".docx":
                text_notes.append(f"--- Файл «{name}» (DOCX) ---\n{_read_docx(path)}")
            elif ext in TEXT_EXTENSIONS or ext == "":
                text_notes.append(f"--- Файл «{name}» ---\n{_read_text_file(path)}")
            else:
                text_notes.append(f"[Файл «{name}» ({ext or 'без расширения'}) — формат не поддерживается для анализа]")
        except Exception as exc:
            text_notes.append(f"[Ошибка чтения «{name}»: {exc}]")
    return text_notes, images