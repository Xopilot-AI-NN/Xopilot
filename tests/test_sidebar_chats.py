"""Sidebar refresh, filtering and selecting actual chat IDs."""
import unittest
from unittest.mock import Mock
import flet as ft
from App.app.menu import build_menu_overlay


class SidebarTests(unittest.IsolatedAsyncioTestCase):
    async def test_sidebar_refetches_filters_and_selects_correct_chat(self):
        page = Mock(width=900)
        rail = ft.Container()
        items = [(17, 'Проект Лилия', 'Сообщений: 4', False), (-25, 'Защищённый анонимный чат', 'Закрыт паролем', False)]
        fetch = Mock(side_effect=lambda: list(items))
        selected = Mock()
        overlay, toggle = build_menu_overlay(rail, page, get_chat_items=fetch,
            get_active_chat_id=lambda: 17, on_select_chat=selected)
        await toggle()
        panel = overlay.controls[1]
        history = panel.content.controls[1]
        search, feedback, rows = history.controls[1:]
        self.assertTrue(history.visible)
        self.assertEqual(len(rows.controls), 2)
        self.assertIsNotNone(rows.controls[0].border)
        search.value = 'лилия'
        search.on_change(None)
        self.assertEqual(len(rows.controls), 1)
        search.value = 'нет совпадений'
        search.on_change(None)
        self.assertTrue(feedback.visible)
        search.value = ''
        search.on_change(None)
        await rows.controls[1].on_click(None)
        selected.assert_called_once_with(-25)
        self.assertFalse(overlay.visible)
        items[0] = (17, 'Новое имя проекта', 'Сообщений: 5', False)
        await toggle()
        self.assertEqual(rows.controls[0].content.controls[1].controls[0].value, 'Новое имя проекта')
        self.assertEqual(fetch.call_count, 2)

    async def test_open_sidebar_refreshes_titles_when_generation_finishes(self):
        page = Mock(width=900)
        items = [(1, 'Новый чат', 'Сообщений: 0', False)]
        overlay, toggle = build_menu_overlay(ft.Container(), page, get_chat_items=lambda: items)
        await toggle()
        rows = overlay.controls[1].content.controls[1].controls[-1]
        items[0] = (1, 'Ответь про орбиту', 'Сообщений: 2', False)
        overlay._xopilot_refresh_chats()
        self.assertEqual(rows.controls[0].content.controls[1].controls[0].value, 'Ответь про орбиту')

    async def test_storage_error_has_visible_feedback(self):
        page = Mock(width=380)
        overlay, toggle = build_menu_overlay(ft.Container(), page, get_chat_items=Mock(side_effect=OSError('disk error')))
        await toggle()
        history = overlay.controls[1].content.controls[1]
        self.assertIn('Не удалось', history.controls[2].value)
        self.assertTrue(history.controls[2].visible)
        self.assertLessEqual(overlay.controls[1].width, 348)
