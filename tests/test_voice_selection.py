"""
Файл: tests/test_voice_selection.py
Разработчик: DenBroLiik
Описание: Сохранение голоса, работа селектора и смена реальной маршрутизации Live ru/en.
"""

import threading
import unittest
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch

from App.services import speech_output, voice_catalog, voice_settings
from App.settings.voice.main import build_voice_page


class VoiceSettingsTests(unittest.TestCase):
    def test_missing_or_invalid_saved_voice_defaults_to_cove(self):
        for saved in (None, "", "obsolete", "cove"):
            with patch.object(voice_settings, "get_setting", return_value=saved):
                self.assertEqual(voice_settings.get_selected_voice(), "cove")

    def test_voice_selection_survives_a_new_reader(self):
        stored = {}
        def save(key, value):
            stored[key] = value
            return True
        with patch.object(voice_settings, "get_setting", side_effect=lambda key, default: stored.get(key, default)), \
                patch.object(voice_settings, "set_setting", side_effect=save), \
                patch.object(voice_catalog.VoiceModel, "installed", new_callable=lambda: property(lambda _: True)):
            for voice in ("miku", "maple", "cove"):
                voice_settings.set_selected_voice(voice)
                self.assertEqual(voice_settings.get_selected_voice(), voice)
        self.assertEqual(stored, {"live_voice": "cove"})

    def test_unavailable_or_unknown_voice_does_not_change_saved_selection(self):
        with patch.object(voice_settings, "set_setting") as save, \
                patch.object(voice_catalog.VoiceModel, "installed", new_callable=lambda: property(lambda _: False)):
            with self.assertRaisesRegex(RuntimeError, "Miku"):
                voice_settings.set_selected_voice("miku")
            with self.assertRaises(ValueError):
                voice_settings.set_selected_voice("unknown")
            save.assert_not_called()

    def test_database_failure_is_reported(self):
        with patch.object(voice_settings, "require_voice"), \
                patch.object(voice_settings, "set_setting", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Не удалось сохранить"):
                voice_settings.set_selected_voice("maple")


class SpeechRoutingTests(unittest.TestCase):
    def setUp(self):
        self.selected = "cove"
        self.calls = []
        self.loaded = []
        self.on_speak = lambda: None

        def build(variant):
            self.loaded.append(variant)
            def speak(text, cancelled):
                self.calls.append((variant, text))
                self.on_speak()
            return Mock(speak=Mock(side_effect=speak))

        patches = [
            patch.object(speech_output, "get_selected_voice", side_effect=lambda: self.selected),
            patch.object(speech_output, "require_voice", side_effect=lambda key: voice_catalog.VOICES[key]),
            patch.object(speech_output, "PiperSpeechVoice", side_effect=build),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_each_profile_routes_russian_and_english_to_its_variants(self):
        speaker = speech_output.SpeechOutput()
        for selected in voice_catalog.VOICES:
            self.selected = selected
            speaker.speak("Привет! Hello!", threading.Event())
        self.assertEqual([call[0] for call in self.calls], [
            variant for voice in voice_catalog.VOICES.values() for variant in (voice.ru, voice.en)
        ])

    def test_voice_change_applies_on_next_reply_without_restarting_live(self):
        speaker = speech_output.SpeechOutput()
        speaker.speak("Первая реплика", threading.Event())
        self.selected = "miku"
        speaker.speak("Вторая реплика", threading.Event())
        self.selected = "maple"
        speaker.speak("Третья реплика", threading.Event())
        self.assertEqual([call[0] for call in self.calls], [voice_catalog.VOICES[key].ru for key in ("cove", "miku", "maple")])
        self.assertEqual(len(speaker._voices), 1)

    def test_change_during_reply_does_not_mix_profiles(self):
        speaker = speech_output.SpeechOutput()
        self.on_speak = lambda: setattr(self, "selected", "miku")
        speaker.speak("Привет! Hello!", threading.Event())
        self.assertEqual([call[0] for call in self.calls], [voice_catalog.VOICES["cove"].ru, voice_catalog.VOICES["cove"].en])
        speaker.speak("Следующая реплика", threading.Event())
        self.assertEqual(self.calls[-1][0], voice_catalog.VOICES["miku"].ru)

    def test_model_is_reused_between_replies_in_same_language(self):
        speaker = speech_output.SpeechOutput()
        speaker.speak("Привет!", threading.Event())
        speaker.speak("До встречи!", threading.Event())
        self.assertEqual(len(self.loaded), 1)

    def test_cancellation_between_languages_does_not_load_next_model(self):
        cancelled = threading.Event()
        speaker = speech_output.SpeechOutput()
        self.on_speak = cancelled.set
        with self.assertRaises(CancelledError):
            speaker.speak("Привет! Hello!", cancelled)
        self.assertEqual(len(self.loaded), 1)

    def test_fixed_voice_can_be_used_without_changing_saved_selection(self):
        speaker = speech_output.SpeechOutput(voice_id="maple")
        self.selected = "miku"
        speaker.speak("Привет!", threading.Event())
        self.assertEqual(self.calls[0][0], voice_catalog.VOICES["maple"].ru)

    def test_cancelled_or_empty_reply_does_not_load_model(self):
        speaker = speech_output.SpeechOutput()
        speaker.speak("  ", threading.Event())
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(CancelledError):
            speaker.speak("Привет!", cancelled)
        self.assertFalse(self.loaded)

    def test_names_do_not_switch_language_inside_russian_sentence(self):
        self.assertEqual(speech_output.speech_segments("Привет, Miku! Как дела? Hello, Maple! 2026."), [
            ("ru", "Привет, Miku! Как дела?"), ("en", "Hello, Maple! 2026."),
        ])

    def test_numbers_keep_previous_language(self):
        self.assertEqual(speech_output.speech_segments("42", "en"), [("en", "42")])
        self.assertEqual(speech_output.speech_segments("42", "ru"), [("ru", "42")])

    def test_markup_is_suitable_for_reading_aloud(self):
        self.assertEqual(speech_output.spoken_text("## Ответ\n**Привет**, [мир](https://example.com)."), "Ответ\nПривет, мир.")

    def test_missing_selected_voice_is_not_replaced_with_another_voice(self):
        with patch.object(speech_output, "require_voice", side_effect=RuntimeError("Голос Miku не установлен")):
            with self.assertRaisesRegex(RuntimeError, "Miku"):
                speech_output.SpeechOutput("miku")
        self.assertFalse(self.loaded)


class VoicePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_selector_has_three_voices_and_saves_choice(self):
        page, status = Mock(), Mock()
        with patch("App.settings.voice.main.get_selected_voice", return_value="maple"), \
                patch("App.settings.voice.main.set_selected_voice") as save:
            content = build_voice_page(page, status)
            select = content.controls[3]
            self.assertEqual(select.value, "maple")
            self.assertEqual(len(select.content.controls), 3)
            select.value = "miku"
            await select.on_change(None)
            save.assert_called_once_with("miku")
            self.assertEqual(select.value, "miku")
            self.assertFalse(select.disabled)
            self.assertIn("Miku", status.call_args.args[0])

    async def test_missing_saved_voice_uses_default_choice(self):
        page, status = Mock(), Mock()
        with patch("App.settings.voice.main.get_selected_voice", return_value=None), \
                patch("App.settings.voice.main.set_selected_voice") as save:
            content = build_voice_page(page, status)
            select = content.controls[3]
            self.assertEqual(select.value, "cove")
            self.assertEqual(len(select.content.controls), 3)
            self.assertFalse(save.called)

    async def test_failed_save_restores_previous_choice_and_reports_error(self):
        page, status = Mock(), Mock()
        with patch("App.settings.voice.main.get_selected_voice", return_value="cove"), \
                patch("App.settings.voice.main.set_selected_voice", side_effect=RuntimeError("БД недоступна")):
            content = build_voice_page(page, status)
            select = content.controls[3]
            select.value = "maple"
            await select.on_change(None)
            self.assertEqual(select.value, "cove")
            self.assertFalse(select.disabled)
            self.assertEqual(status.call_args.args[0], "Голос не изменён")
            self.assertEqual(content.controls[4].value, "БД недоступна")


if __name__ == "__main__":
    unittest.main()
