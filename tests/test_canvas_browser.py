"""
Файл: /tests/test_canvas_browser.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Проверка стабильного размера страницы при показе индикатора загрузки.
          Исполнитель: Codex.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from App.app.canvas.canvas_browser import show_browser


class BrowserLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_updates_do_not_restart_viewport_resize(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'page.png';path.write_bytes(b'png')
            frame={'screenshot':str(path),'width':800,'height':500,'title':'Test'}
            service=Mock();service.inspect.return_value=frame
            tasks=[]
            def schedule(fn,*args):
                task=asyncio.create_task(fn(*args));tasks.append(task);return task
            page=Mock(width=1000,height=800);page.run_task=schedule
            dialog=show_browser(page,service,1,'project','doc',frame,'Test')
            column=dialog.content.content;surface=column.controls[2];progress=column.controls[1]
            event=SimpleNamespace(width=800.1,height=500.1)
            page.update.side_effect=lambda:surface.on_size_change(event)
            surface.on_size_change(event)
            await asyncio.gather(*tasks)
            service.inspect.assert_called_once()
            self.assertEqual(len(tasks),1)
            self.assertEqual(progress.height,2);self.assertTrue(progress.visible);self.assertEqual(progress.opacity,0)
            surface.on_size_change(event)
            self.assertEqual(len(tasks),1)
