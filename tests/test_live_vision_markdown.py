"""
Файл: tests/test_live_vision_markdown.py
Разработчик: DenBroLiik
Описание: Захват кадра экрана (Wayland/чёрный кадр), причина ошибки камеры/экрана в Live
    и Markdown-рендер ответов ИИ — без устройств, БД и модели.
"""

import io
import unittest
from unittest.mock import Mock, patch

import flet as ft
from PIL import Image

from App.app.live_conversation import LiveConversation
from App.app.message import build_ai_message
from App.services import live_vision


def solid(color):
    return Image.new("RGB", (64, 32), color)


class ScreenCaptureTests(unittest.TestCase):
    def test_wayland_uses_compositor_tool_before_mss(self):
        with patch.object(live_vision, "_is_wayland", return_value=True), \
                patch.object(live_vision, "_grab_cli", return_value=solid((90, 120, 200))) as cli, \
                patch.object(live_vision, "_grab_mss") as x11:
            data = live_vision.capture_screen_frame()
        x11.assert_not_called()
        cli.assert_called_once()
        self.assertEqual(Image.open(io.BytesIO(data)).format, "JPEG")

    def test_black_mss_frame_falls_back_to_compositor_tool(self):
        with patch.object(live_vision, "_is_wayland", return_value=False), \
                patch.object(live_vision, "_grab_mss", return_value=solid((0, 0, 0))), \
                patch.object(live_vision, "_grab_cli", return_value=solid((200, 200, 200))):
            self.assertTrue(live_vision.capture_screen_frame().startswith(b"\xff\xd8"))

    def test_black_frame_is_reported_instead_of_sent_to_model(self):
        with patch.object(live_vision, "_is_wayland", return_value=True), \
                patch.object(live_vision, "_grab_cli", return_value=solid((0, 0, 0))), \
                patch.object(live_vision, "_grab_mss", return_value=solid((0, 0, 0))):
            with self.assertRaisesRegex(RuntimeError, "чёрный"):
                live_vision.capture_screen_frame()

    def test_missing_tools_are_reported_with_reason(self):
        with patch.object(live_vision, "_is_wayland", return_value=True), \
                patch.object(live_vision.shutil, "which", return_value=None), \
                patch.object(live_vision, "_grab_mss", side_effect=RuntimeError("не установлен mss")):
            with self.assertRaisesRegex(RuntimeError, "spectacle"):
                live_vision.capture_screen_frame()


class LiveVisionNoteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.live = LiveConversation(Mock(web=False), lambda: False, list, Mock(), Mock())
        self.live._set_state = Mock()

    async def test_capture_error_is_remembered_and_reply_continues_without_image(self):
        self.live.camera_on = True
        with patch("App.app.live_conversation.capture_camera_frame", side_effect=RuntimeError("Нет камеры.")):
            self.assertIsNone(await self.live._capture_vision_frame())
        self.assertIn("Нет камеры.", self.live._vision_note)
        self.assertIn("Камера", self.live._vision_note)

    async def test_screen_frame_is_returned_and_note_is_cleared(self):
        self.live.screen_on = True
        self.live._vision_note = "старая ошибка"
        with patch("App.app.live_conversation.capture_screen_frame", return_value=b"jpeg"):
            self.assertEqual(await self.live._capture_vision_frame(), b"jpeg")
        self.assertEqual(self.live._vision_note, "")

    async def test_no_vision_button_means_no_capture(self):
        with patch("App.app.live_conversation.capture_camera_frame") as camera, \
                patch("App.app.live_conversation.capture_screen_frame") as screen:
            self.assertIsNone(await self.live._capture_vision_frame())
        camera.assert_not_called()
        screen.assert_not_called()


def find_all(control, kind):
    found = [control] if isinstance(control, kind) else []
    for child in getattr(control, "controls", None) or []:
        found += find_all(child, kind)
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        found += find_all(content, kind)
    return found


class MarkdownMessageTests(unittest.TestCase):
    def test_ai_reply_is_rendered_as_markdown(self):
        raw = "**Жирный**, *курсив* и `код`\n\n- пункт"
        markdown = find_all(build_ai_message(raw), ft.Markdown)
        self.assertEqual(len(markdown), 1)
        self.assertEqual(markdown[0].value, raw)
        self.assertEqual(markdown[0].extension_set, ft.MarkdownExtensionSet.GITHUB_FLAVORED)

    def test_author_prefix_stays_bold(self):
        markdown = find_all(build_ai_message("Zephyr: привет"), ft.Markdown)[0]
        self.assertEqual(markdown.value, "**Zephyr**: привет")

    def test_copy_action_gets_raw_markdown(self):
        calls = []

        async def on_action(*args):
            calls.append(args)

        message = build_ai_message("**текст**", on_action=on_action, message_id=7)
        button = find_all(message, ft.IconButton)[0]
        import asyncio
        asyncio.run(button.on_click(None))
        self.assertEqual(calls, [("copy", "**текст**", None, 7)])


if __name__ == "__main__":
    unittest.main()