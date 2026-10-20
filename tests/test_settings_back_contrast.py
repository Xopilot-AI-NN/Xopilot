"""
Файл: /tests/test_settings_back_contrast.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Проверяю видимость стрелки назад во всех темах. Исполнитель: Codex.
"""
import unittest
from unittest.mock import Mock
from App.settings.buttons.back import build_back_button
from App.app.theme import palette


def luminance(value):
    rgb=[int(str(value)[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))


class BackContrastTests(unittest.TestCase):
    def test_back_remains_visible_when_theme_changes(self):
        button=build_back_button(Mock())
        try:
            for theme in palette.THEMES:
                with self.subTest(theme=theme):
                    palette.set_theme(Mock(controls=[button],overlay=[]),theme)
                    dark,light=sorted([luminance(button.icon_color),luminance(palette.color('#eafffa'))])
                    self.assertGreaterEqual((light+.05)/(dark+.05),3)
        finally:palette.set_theme(Mock(controls=[],overlay=[]),'light')
