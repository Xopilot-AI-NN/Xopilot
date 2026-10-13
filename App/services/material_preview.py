"""Bounded document previews and streamed exports of app-managed materials."""
import base64
import io
import json
import shutil
from pathlib import Path
from . import storage
from .db import get_db
from .paths import app_data_dir
from .attachments import TEXT_EXTENSIONS, IMAGE_EXTENSIONS

TEXT_PREVIEW_BYTES = 64 * 1024
WEB_EXPORT_BYTES = 16 * 1024 * 1024
_private_paths={}


def authorize_private(path,session,cid):
    import weakref
    _private_paths[str(path)]=(weakref.ref(session),cid)


def resolve(path):
    path = Path(path)
    registered=_private_paths.get(str(path))
    if registered:
        session=registered[0]()
        if session and session.opened(registered[1]) and path.is_file() and not path.is_symlink():return path
        raise ValueError('Защищённый чат закрыт: материал недоступен')
    try:
        storage._managed(path)
    except ValueError:
        root = app_data_dir() / 'material-trash'
        if path.parent != root or path.is_symlink() or root.is_symlink():
            raise ValueError('Можно просматривать только материалы Xopilot') from None
        items = json.loads(get_db().get_setting('material_trash_v1') or '{}')
        if path.name not in items:
            raise ValueError('Файл корзины не найден') from None
    if not path.is_file():
        raise ValueError('Копия материала недоступна. Скачайте её из облака или восстановите из корзины')
    return path


def preview(path, name):
    path = resolve(path)
    extension = Path(name).suffix.lower()
    result = {'bytes': path.stat().st_size, 'text': '', 'image': '', 'truncated': False}
    if extension in TEXT_EXTENSIONS or extension in {'.svg'}:
        with path.open('rb') as source:
            raw = source.read(TEXT_PREVIEW_BYTES + 1)
        result['truncated'] = len(raw) > TEXT_PREVIEW_BYTES
        result['text'] = raw[:TEXT_PREVIEW_BYTES].decode('utf-8-sig', errors='replace')
    elif extension in IMAGE_EXTENSIONS:
        from PIL import Image, ImageOps
        with Image.open(path) as image:
            # Bound decompression before loading pixels, including crafted images.
            if image.width * image.height > 20_000_000:
                result['text'] = 'Изображение слишком большое для встроенного просмотра. Сохраните оригинал, чтобы открыть его.'
                return result
            image.draft('RGB', (1280, 1280))
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1280, 1280))
            output = io.BytesIO();image.convert('RGB').save(output, format='JPEG', quality=80)
        result['image'] = 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
    elif extension in {'.pdf', '.docx'} and result['bytes'] <= WEB_EXPORT_BYTES:
        from .attachments import build_attachment_message_parts
        notes, _ = build_attachment_message_parts([(name, str(path))])
        result['text'] = '\n\n'.join(notes)
        result['truncated'] = True
    else:
        result['text'] = 'Встроенный просмотр этого формата недоступен. Сохраните файл, чтобы открыть его в подходящем приложении.'
    return result


def copy_to(path, destination):
    """Stream a copy, never overwrite the managed source with itself."""
    source = resolve(path)
    target = Path(destination)
    if target.resolve() == source.resolve():
        raise ValueError('Выберите место вне исходной копии материала')
    # Never export on top of another managed material/database/vault.
    try:
        target.resolve().relative_to(app_data_dir().resolve())
    except ValueError:
        pass
    else:
        raise ValueError('Выберите папку вне внутреннего хранилища Xopilot')
    shutil.copyfile(source, target)
    return str(target)
