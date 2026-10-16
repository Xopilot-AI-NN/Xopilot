"""
Файл: /App/app/materials/file_selection.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент file_selection интерфейса Xopilot.
"""
"""Native and local web file selection share managed attachment storage.

Flet 1 registers services on construction inside a page callback. Adding that
same picker to page.services also binds it to the view lifecycle; two registries
then own the same method listener, which can leave pick_files without a handler.
"""
import asyncio
from .material import file_from_path
try:
    from ...services.platforms import is_android
    from ...services.material_store import store_material
except ImportError:
    from services.platforms import is_android
    from services.material_store import store_material


async def pick_materials(page, picker, *, store=None):
    selected = await picker.pick_files(dialog_title='Выберите материалы', allow_multiple=True,
                                       with_data=bool(page.web))
    result = []
    for file in selected or []:
        data = file.bytes
        # Android's picker streams SAF documents to its app-private cache and
        # returns that readable path. Avoid with_data: it buffers whole files in
        # Flutter and copies them again through the Python bridge.
        path = file.path
        picked_path = path
        if data is None and (not path or str(path).startswith("content://")):
            raise RuntimeError('Системный выбор файлов не предоставил содержимое документа. Выберите файл повторно.')
        if data is not None:
            path = None
        try:
            path = await asyncio.to_thread(store or store_material, file.name,
                                           path=path, data=data)
        finally:
            if is_android() and picked_path:
                try:
                    from ...services.mobile_runtime import call_async
                except ImportError:
                    from services.mobile_runtime import call_async
                await call_async('discardPickedFile', {'path': str(picked_path)})
        result.append(file_from_path(path))
    return result
