"""
Файл: /tests/test_android_voice_preview.py
Разработчик: DenBroLiik
Версия: 2.0.9
Описание: Частичная готовность языков Android не маскирует успешную озвучку.
"""
import unittest
from unittest.mock import Mock,patch,AsyncMock
from App.settings.voice import android as ui

class AndroidVoicePreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_english_does_not_hide_successful_russian(self):
        page=Mock();status=Mock()
        with patch.object(ui,'call_async',AsyncMock(return_value={'engines':[{'id':'rhvoice'}]})),\
                patch.object(ui,'AndroidSpeechOutput') as output:
            output.return_value.speak.side_effect=[None,RuntimeError('Установите офлайн-голос en')]
            controls=ui.build_android_voice_controls(page,status)
            button=controls.controls[2].controls[-1]
            await button.on_click(None)
        self.assertEqual(output.return_value.speak.call_count,2)
        self.assertIn('Русский: озвучено',controls.controls[-1].value)
        self.assertIn('офлайн-голос en',controls.controls[-1].value)
        status.assert_called_once_with('Озвучивание проверено частично')
        self.assertFalse(button.disabled)

    async def test_no_engine_is_actionable_and_does_not_try_to_speak(self):
        with patch.object(ui,'call_async',AsyncMock(return_value={'engines':[]})),patch.object(ui,'AndroidSpeechOutput') as output:
            controls=ui.build_android_voice_controls(Mock(),Mock())
            await controls.controls[2].controls[-1].on_click(None)
        output.assert_not_called()
        self.assertIn('установите движок',controls.controls[-1].value)
