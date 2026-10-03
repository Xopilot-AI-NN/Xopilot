"""Native and local web file selection share managed attachment storage.

Flet 1 registers services on construction inside a page callback. Adding that
same picker to page.services also binds it to the view lifecycle; two registries
then own the same method listener, which can leave pick_files without a handler.
"""
import asyncio
from .material import file_from_path
try:
    from ..services.material_store import store_material
except ImportError:
    from services.material_store import store_material


async def pick_materials(page, picker, *, store=None):
    selected = await picker.pick_files(dialog_title='Выберите материалы', allow_multiple=True,
                                       with_data=bool(page.web))
    result = []
    for file in selected or []:
        path = await asyncio.to_thread(store or store_material, file.name,
                                       path=file.path, data=file.bytes)
        result.append(file_from_path(path))
    return result
