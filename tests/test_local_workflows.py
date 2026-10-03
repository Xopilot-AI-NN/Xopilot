"""Cross-feature regressions using temporary data and actual native storage."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import flet as ft
from App.services import workspaces, drafts, material_store, live_vision
from App.services.db import advanced_xopilot
from App.app.live_conversation import LiveConversation
from App.app import palette
import test_real_answers


@unittest.skipIf(advanced_xopilot is None, 'Native database is required')
class LocalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / 'data.db'
        self.db = advanced_xopilot.PyDatabase(str(self.db_path))
        for module in (workspaces, drafts):
            patcher = patch.object(module, 'get_db', side_effect=lambda: self.db)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(material_store, 'app_data_dir', return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: setattr(self, 'db', None))

    def test_shared_files_and_instructions_survive_restart_and_original_move(self):
        original = self.root / 'brief.txt'
        original.write_text('Код проекта — ЛИЛИЯ', encoding='utf-8')
        managed = material_store.store_material(original.name, path=original)
        item = workspaces.create_workspace('Проект')
        workspaces.update_workspace(item['id'], 'Проект', 'Отвечай по документам',
                                    [{'name': original.name, 'path': managed}])
        chat = self.db.create_chat('Работа')
        workspaces.assign_chat(chat, item['id'])
        drafts.write_draft(chat, 'Черновик', [managed])
        original.unlink()
        self.db = None
        self.db = advanced_xopilot.PyDatabase(str(self.db_path))
        self.assertEqual(workspaces.chat_resources(chat), ('Отвечай по документам', [('brief.txt', managed)]))
        self.assertEqual(Path(managed).read_text(encoding='utf-8'), 'Код проекта — ЛИЛИЯ')
        self.assertEqual(drafts.read_draft(chat), {'text': 'Черновик', 'files': [managed]})
        workspaces.assign_chat(chat, 'all')
        self.assertEqual(workspaces.chat_resources(chat), ('', []))
        self.assertEqual(len(self.db.list_chats()), 1)

    def test_web_material_bytes_are_saved_without_client_path(self):
        path = material_store.store_material('../brief.txt', data=b'contents')
        self.assertEqual(Path(path).name, 'brief.txt')
        self.assertEqual(Path(path).read_bytes(), b'contents')
        self.assertTrue(Path(path).is_relative_to(self.root))

    def test_failed_import_leaves_no_partial_file(self):
        with self.assertRaises(FileNotFoundError):
            material_store.store_material('brief.txt', path=self.root / 'missing.txt')
        self.assertEqual(list((self.root / 'materials').iterdir()), [])


class CameraLifetimeTests(unittest.TestCase):
    def test_closed_camera_cannot_reopen_after_late_capture(self):
        camera = live_vision.CameraStream()
        camera.close()
        with patch.object(live_vision, 'cv2') as cv:
            with self.assertRaisesRegex(RuntimeError, 'отключена'):
                camera.frame()
            cv.VideoCapture.assert_not_called()


class LivePreviewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.live = LiveConversation(Mock(web=False), lambda: False, list, Mock(), Mock())
        self.live._refresh_vision_buttons = Mock()

    async def test_idle_preview_is_released_by_stop(self):
        self.live.camera_on = True
        camera = Mock()
        self.live._camera = camera
        self.live._preview_task = __import__('asyncio').create_task(__import__('asyncio').sleep(60))
        await self.live.stop()
        camera.close.assert_called_once()
        self.assertIsNone(self.live._preview_task)
        self.assertFalse(self.live.camera_on)
        self.assertFalse(self.live.visual_panel.visible)

    async def test_stale_frame_is_not_sent(self):
        self.live.screen_on = True
        self.live._last_frame = b'old'
        self.live._last_source = 'screen'
        self.live._last_frame_time = time.monotonic() - 10
        with patch('App.app.live_conversation.capture_screen_frame', return_value=b'fresh'):
            self.assertEqual(await self.live._capture_vision_frame(), b'fresh')

    async def test_controller_can_restart_after_browser_reconnect(self):
        await self.live.close()
        self.assertTrue(self.live._closed)
        self.live.reconnect()
        self.assertFalse(self.live._closed)
        self.assertFalse(self.live.busy)


class RetryUITests(unittest.IsolatedAsyncioTestCase):
    setUp = test_real_answers.PersistenceUITests.setUp

    async def test_worker_cancellation_offers_retry_without_duplicate_question(self):
        from concurrent.futures import CancelledError
        self.generate.side_effect = [CancelledError(), 'Повторный ответ']
        self.prompt.value = 'Вопрос'
        await self.send(None)
        composer = self.prompt_container.call_args.kwargs['composer_status']
        retry = composer.content.controls[-1]
        self.assertTrue(composer.visible)
        self.assertTrue(retry.visible)
        await retry.on_click(None)
        self.assertEqual(self.save.call_count, 1)
        self.assertFalse(retry.visible)

    async def test_retry_uses_edited_question(self):
        from concurrent.futures import CancelledError
        from unittest.mock import AsyncMock
        self.generate.side_effect = [CancelledError(), 'Ответ на правку']
        self.prompt.value = 'Старый вопрос'
        await self.send(None)
        action = self.user.call_args.kwargs['on_action']
        self.prompt.focus = AsyncMock()
        await action('edit', 'Старый вопрос', [], 11)
        composer = self.prompt_container.call_args.kwargs['composer_status']
        self.assertFalse(composer.content.controls[-1].visible)
        self.prompt.value = 'Исправленный вопрос'
        await self.send(None)
        composer = self.prompt_container.call_args.kwargs['composer_status']
        await composer.content.controls[-1].on_click(None)
        self.assertEqual(self.generate.call_args.args[0], 'Исправленный вопрос')
        self.assertEqual(self.save.call_count, 1)

    async def test_retry_preserves_new_draft_and_does_not_repeat_user_message(self):
        self.generate.side_effect = [RuntimeError('inference failed'), 'Ответ']
        self.prompt.value = 'Вопрос'
        await self.send(None)
        self.prompt.value = 'Следующий черновик'
        composer = self.prompt_container.call_args.kwargs['composer_status']
        retry = composer.content.controls[-1]
        self.assertTrue(retry.visible)
        await retry.on_click(None)
        self.assertEqual(self.save.call_count, 1)
        self.assertEqual(self.generate.call_count, 2)
        self.assertEqual(self.prompt.value, 'Следующий черновик')
        self.assertFalse(retry.visible)


class PaletteTests(unittest.TestCase):
    def test_theme_replaces_shared_border_styles_without_changing_shape(self):
        original = ft.Border.all(2, '#ffffff')
        panel = ft.Container(border=original, border_radius=25)
        page = Mock(controls=[panel], overlay=[])
        palette.set_theme(page, 'dark')
        self.addCleanup(palette.set_theme, page, 'light')
        self.assertEqual(original.top.color, '#ffffff')
        for side in ('top', 'right', 'bottom', 'left'):
            self.assertEqual(getattr(panel.border, side).color, '#24434b')
        self.assertEqual(panel.border_radius, 25)
        palette.set_theme(page, 'light')
        for side in ('top', 'right', 'bottom', 'left'):
            self.assertEqual(getattr(panel.border, side).color, '#ffffff')
        self.assertEqual(panel.border_radius, 25)

    def test_settings_sections_construct_with_readable_dark_text(self):
        from App.settings.main import build_settings_dialog
        page = Mock(controls=[], overlay=[], width=420, height=760)
        palette.install_theme(page, 'dark')
        self.addCleanup(palette.set_theme, page, 'light')
        with patch('App.settings.account.main.get_stats', return_value={'app_seconds': 60, 'messages': 2, 'tokens': 10}), \
             patch('App.settings.account.main.get_setting', side_effect=lambda key, default=None: default):
            for index in (0, 2, 3, 4, 5):
                with self.subTest(section=index):
                    dialog = build_settings_dialog(page, start_section=index)
                    body = dialog.content.controls[1].content.controls[0].controls[0]
                    # Section builders hold palette constants loaded before theme changes.
                    title = body.controls[0]
                    if isinstance(title, ft.Text):
                        self.assertEqual(title.color, palette.color('#087f8c'))

    def test_dark_theme_changes_surfaces_and_new_dialogs_then_restores_light(self):
        panel = ft.Container(bgcolor='#d9ffe6', content=ft.Text('Текст', color='#123b43'))
        page = Mock(controls=[panel], overlay=[])
        show = page.show_dialog
        palette.install_theme(page, 'dark')
        dialog = ft.AlertDialog(bgcolor='#eafffa', title=ft.Text('Окно', color='#123b43'))
        page.show_dialog(dialog)
        self.assertEqual(panel.bgcolor, '#152f31')
        self.assertEqual(dialog.title.color, '#e4f6f7')
        show.assert_called_once_with(dialog)
        palette.set_theme(page, 'light')
        self.assertEqual(panel.bgcolor, '#d9ffe6')
        self.assertEqual(panel.content.color, '#123b43')
