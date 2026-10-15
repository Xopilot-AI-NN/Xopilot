"""
Файл: /tests/test_canvas_web.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Настоящие JavaScript, формы и очистка браузера Canvas.
          Исполнитель проверок: Codex.
"""
import unittest
from pathlib import Path

class CanvasWebTests(unittest.TestCase):
    def test_real_canvas_javascript_click_fill_and_browser_cleanup(self):
        from App.services.canvas_web import WebSession
        from playwright.sync_api import sync_playwright
        with sync_playwright() as driver:
            if not Path(driver.chromium.executable_path).is_file():
                self.skipTest('Chromium for Canvas is not installed')
        session=WebSession()
        html='<h1>Привет</h1><input id="name"><button id="ok" onclick="this.textContent=document.querySelector(\'#name\').value">Нажми</button>'
        try:
            frame=session.call(html);self.assertIn('Привет',frame['text'])
            session.call(html,{'action':'fill','selector':'#name','text':'Готово'})
            frame=session.call(html,{'action':'click','selector':'#ok'});self.assertIn('Готово',frame['text'])
            self.assertTrue(Path(frame['screenshot']).is_file())
            from PIL import Image
            with Image.open(frame['screenshot']) as image:self.assertEqual(image.size,(960,600))
            edited='<h1>Новая версия</h1><button id=blocked onclick="fetch(\'https://example.invalid/\').catch(()=>this.textContent=\'Сеть заблокирована\')">Проверить</button>'
            frame=session.call(edited);self.assertIn('Новая версия',frame['text'])
            frame=session.call(edited,{'action':'click','selector':'#blocked'})
            frame=session.call(edited);self.assertIn('Сеть заблокирована',frame['text'])
            with self.assertRaises(ValueError):session.call(html,{'action':'click','selector':'body *'})
        finally:session.close()
        self.assertFalse(session.folder.exists())
