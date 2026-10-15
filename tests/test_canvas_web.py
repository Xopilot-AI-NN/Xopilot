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
    def test_responsive_point_click_and_real_back_forward(self):
        from App.services.canvas_web import WebSession
        from playwright.sync_api import sync_playwright
        with sync_playwright() as driver:
            if not Path(driver.chromium.executable_path).is_file():self.skipTest('Chromium not installed')
        session=WebSession()
        html='<button id="go" onclick="location.hash=\'next\';this.textContent=\'Готово\'">Открыть</button>'
        try:
            frame=session.call(html,{'action':'viewport','width':420,'height':700})
            self.assertEqual((frame['width'],frame['height']),(420,700))
            button=frame['elements'][0]
            frame=session.call(html,{'action':'point','x':button['x']+button['width']/2,'y':button['y']+button['height']/2})
            self.assertIn('Готово',frame['text']);self.assertEqual(frame['fragment'],'#next')
            self.assertTrue(frame['can_go_back'])
            frame=session.call(html,{'action':'back'})
            self.assertEqual(frame['fragment'],'');self.assertTrue(frame['can_go_forward'])
            frame=session.call(html,{'action':'forward'})
            self.assertEqual(frame['fragment'],'#next')
        finally:session.close()

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
