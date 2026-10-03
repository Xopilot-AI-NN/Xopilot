"""
Файл: tests/test_real_answers.py
Разработчик: DenBroLiik
Описание: Необрезанные ответы модели и безопасная разовая очистка прежних заглушек.
"""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
from App.app import main as main_ui
from App.services import chat_store, llm


class ModelLimitsTests(unittest.TestCase):
    def test_text_reply_is_not_limited_or_truncated(self):
        answer = "Подробный ответ. " * 1000
        conversation = Mock()
        conversation.send_message.return_value = {"content": [{"text": answer}]}
        with patch.object(llm, "_conversation", conversation), patch.object(llm, "record_generation"):
            self.assertEqual(llm.generate_reply("Расскажи подробно"), answer.strip())
        conversation.send_message.assert_called_once_with("Расскажи подробно")

    def test_history_keeps_more_than_twelve_messages_and_six_thousand_characters(self):
        history = [{"role": "user", "content": "Длинная реплика " * 1000}]
        history += [{"role": "ai", "content": f"Ответ {i}"} for i in range(20)]
        context = Mock()
        conversation = context.__enter__ = Mock(return_value=Mock())
        context.__exit__ = Mock(return_value=False)
        conversation.return_value.send_message.return_value = {"content": [{"text": "Ответ"}]}
        engine = Mock()
        engine.create_conversation.return_value = context
        with patch.multiple(llm, _engine=engine, _conversation=Mock()), patch.object(llm, "record_generation"):
            llm.generate_reply("Следующий вопрос", history=history)
        messages = engine.create_conversation.call_args.kwargs["messages"]
        self.assertEqual(len(messages), len(history))
        self.assertEqual(messages[0]["content"][0]["text"], history[0]["content"])
        conversation.return_value.send_message.assert_called_once_with("Следующий вопрос")

    def test_live_reply_does_not_set_a_token_budget(self):
        conversation = Mock()
        conversation.send_message.return_value = {"content": [{"text": "Развёрнутый ответ"}]}
        context = Mock(__enter__=Mock(return_value=conversation), __exit__=Mock(return_value=False))
        engine = Mock()
        engine.create_conversation.return_value = context
        with patch.object(llm, "_engine", engine), patch.object(llm, "prepare_voice_model"), patch.object(llm, "record_generation"):
            llm.generate_live_reply([{"role": "user", "content": "Расскажи подробно"}], threading.Event())
        self.assertNotIn("max_output_tokens", conversation.send_message.call_args.kwargs)
        self.assertNotIn("max_output_tokens", engine.create_conversation.call_args.kwargs)

    def test_empty_model_response_is_an_error(self):
        conversation = Mock()
        conversation.send_message.return_value = {"content": []}
        with patch.object(llm, "_conversation", conversation), patch.object(llm, "record_generation") as stats:
            with self.assertRaisesRegex(RuntimeError, "не вернула ответ"):
                llm.generate_reply("Привет")
            stats.assert_not_called()


class LegacyCleanupTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        self.settings = {}
        self.db = Mock()
        self.db.list_chats.return_value = [(1, "Продолжение оформления", 0)]
        self.db.get_messages.side_effect = lambda _: list(self.rows)
        self.db.get_setting.side_effect = self.settings.get
        self.db.set_setting.side_effect = self.settings.__setitem__
        def delete(message_id):
            self.rows[:] = [row for row in self.rows if row.id != message_id]
            return True
        self.db.delete_message.side_effect = delete
        patcher = patch.object(chat_store, "get_db", return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, role, content, quote=None, reply_to=None, attachments=None):
        message = SimpleNamespace(id=len(self.rows)+1, role=role, content=content,
                                  quote=quote, reply_to=reply_to, attachments=attachments or [])
        self.rows.append(message)
        return message

    def seed(self):
        for values in chat_store._LEGACY_DEMO:
            self.add(*values)

    def test_exact_demo_and_ai_templates_are_removed_but_real_messages_remain(self):
        self.seed()
        self.add("ai", "Принято. Продолжаем?")
        real_user = self.add("user", "Принято. Продолжаем?")
        real_ai = self.add("ai", "Мой настоящий ответ")
        self.assertEqual(chat_store.cleanup_legacy_messages(), 7)
        self.assertEqual(self.rows, [real_user, real_ai])

    def test_edited_demo_and_quoted_or_attached_messages_are_preserved(self):
        self.seed()
        self.rows[1].content = "Моя изменённая реплика"
        self.add("ai", "Принято. Продолжаем?", quote="Важная цитата")
        self.add("ai", "Принято. Продолжаем?", attachments=[("file.txt", "/tmp/file.txt")])
        self.assertEqual(chat_store.cleanup_legacy_messages(), 0)
        self.assertEqual(len(self.rows), 8)

    def test_future_real_replies_with_same_words_are_not_deleted_again(self):
        chat_store.cleanup_legacy_messages()
        message = self.add("ai", "Принято. Продолжаем?")
        self.assertEqual(chat_store.cleanup_legacy_messages(), 0)
        self.assertEqual(self.rows, [message])

    def test_interrupted_cleanup_resumes_without_removing_edited_remaining_row(self):
        self.seed()
        delete = self.db.delete_message.side_effect
        def fail(message_id):
            if message_id == 3:
                raise RuntimeError("Temporary database failure")
            return delete(message_id)
        self.db.delete_message.side_effect = fail
        with self.assertRaises(RuntimeError):
            chat_store.cleanup_legacy_messages()
        edited = self.rows[0]
        edited.content = "После сбоя пользователь изменил сообщение"
        self.db.delete_message.side_effect = delete
        self.assertEqual(chat_store.cleanup_legacy_messages(), 3)
        self.assertEqual(self.rows, [edited])


class RealReplyUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch.multiple(main_ui, install_theme=Mock(),
                                 read_draft=Mock(return_value={}), write_draft=Mock())
        patcher.start()
        self.addCleanup(patcher.stop)
    async def test_generation_failure_is_shown_without_saving_a_fake_ai_reply(self):
        page = Mock(services=[], web=False)
        prompt = ft.TextField()
        prompt.update = Mock()
        messages = ft.ListView(controls=[])
        messages.update = Mock()
        container = Mock(return_value=ft.Container())
        save_ai = Mock()
        replacements = {
            "build_prompt": Mock(return_value=prompt),
            "build_chat": Mock(return_value=ft.Container(content=messages)),
            "build_prompt_container": container,
            "build_background_layout": Mock(return_value=ft.Container()),
            "build_menu": Mock(return_value=ft.Container()),
            "build_menu_overlay": Mock(return_value=(ft.Container(), Mock())),
            "cleanup_legacy_messages": Mock(),
            "get_or_create_active_chat_id": Mock(return_value=1),
            "load_chat_messages": Mock(return_value=[]),
            "save_user_message": Mock(return_value=1),
            "save_ai_message": save_ai,
            "ensure_model_loaded": Mock(),
            "get_selected_chat_model": Mock(return_value="test.litertlm"),
            "generate_reply": Mock(side_effect=RuntimeError("Ошибка настоящей модели")),
        }
        with patch.multiple(main_ui, **replacements):
            main_ui.build_app_ui(page)
            send = container.call_args.args[1]
            prompt.value = "Мой вопрос"
            await send(None)
        save_ai.assert_not_called()
        self.assertEqual(len(messages.controls), 1)
        self.assertIn("Ошибка настоящей модели", page.show_dialog.call_args.args[0].content.value)

    async def test_absent_model_is_reported_without_generation(self):
        page = Mock(services=[], web=False)
        prompt = ft.TextField()
        prompt.update = Mock()
        messages = ft.ListView(controls=[])
        messages.update = Mock()
        container = Mock(return_value=ft.Container())
        generate = Mock()
        save_ai = Mock()
        with patch.multiple(main_ui,
                            build_prompt=Mock(return_value=prompt),
                            build_chat=Mock(return_value=ft.Container(content=messages)),
                            build_prompt_container=container,
                            build_background_layout=Mock(return_value=ft.Container()),
                            build_menu=Mock(return_value=ft.Container()),
                            build_menu_overlay=Mock(return_value=(ft.Container(), Mock())),
                            cleanup_legacy_messages=Mock(),
                            get_or_create_active_chat_id=Mock(return_value=1),
                            load_chat_messages=Mock(return_value=[]),
                            save_user_message=Mock(return_value=1), save_ai_message=save_ai,
                            ensure_model_loaded=Mock(),
                            get_selected_chat_model=Mock(return_value=None), generate_reply=generate):
            main_ui.build_app_ui(page)
            prompt.value = "Мой вопрос"
            await container.call_args.args[1](None)
        generate.assert_not_called()
        save_ai.assert_not_called()
        self.assertIn("модель не найдена", page.show_dialog.call_args.args[0].content.value)
        status = container.call_args.kwargs['composer_status']
        self.assertTrue(status.visible)
        self.assertIn('Настройки → Модели', status.content.controls[0].value)
        self.assertTrue(status.content.controls[-1].visible)


class PersistenceUITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock(services=[], web=False)
        self.prompt = ft.TextField()
        self.prompt.update = Mock()
        self.messages = ft.ListView(controls=[])
        self.messages.update = Mock()
        self.prompt_container = Mock(return_value=ft.Container())
        self.menu = Mock(return_value=ft.Container())
        self.user = Mock(side_effect=lambda text, *a, **kw: ft.Container(data=kw.get("message_id")))
        self.save = Mock(return_value=11)
        self.generate = Mock(return_value="Ответ")
        self.delete = Mock(return_value=True)
        self.update = Mock(return_value=True)
        self.save_ai = Mock(return_value=12)
        replacements = dict(
            install_theme=Mock(), read_draft=Mock(return_value={}), write_draft=Mock(),
            build_prompt=Mock(return_value=self.prompt),
            build_chat=Mock(return_value=ft.Container(content=self.messages)),
            build_prompt_container=self.prompt_container,
            build_background_layout=Mock(return_value=ft.Container()),
            build_menu=self.menu,
            build_menu_overlay=Mock(return_value=(ft.Container(), Mock())),
            build_user_message=self.user,
            cleanup_legacy_messages=Mock(), get_or_create_active_chat_id=Mock(return_value=1),
            load_chat_messages=Mock(return_value=[]), save_user_message=self.save,
            save_ai_message=self.save_ai, get_selected_chat_model=Mock(return_value="test.litertlm"),
            ensure_model_loaded=Mock(), generate_reply=self.generate,
            store_delete_message=self.delete, update_message=self.update,
        )
        patcher = patch.multiple(main_ui, **replacements)
        patcher.start()
        self.addCleanup(patcher.stop)
        main_ui.build_app_ui(self.page)
        self.send = self.prompt_container.call_args.args[1]

    async def test_failed_save_preserves_draft_and_does_not_generate(self):
        self.save.side_effect = RuntimeError("disk full")
        self.prompt.value = "Важный черновик"
        await self.send(None)
        self.assertEqual(self.prompt.value, "Важный черновик")
        self.assertEqual(self.messages.controls, [])
        self.generate.assert_not_called()
        self.assertIn("disk full", self.page.show_dialog.call_args.args[0].content.value)

    async def test_failed_delete_keeps_message_visible(self):
        self.prompt.value = "Вопрос"
        await self.send(None)
        action = self.user.call_args.kwargs["on_action"]
        before = list(self.messages.controls)
        self.delete.side_effect = RuntimeError("disk error")
        await action("delete", "Вопрос", [], 11)
        self.assertEqual(self.messages.controls, before)

    async def test_failed_edit_preserves_original_and_draft(self):
        self.prompt.value = "Вопрос"
        await self.send(None)
        action = self.user.call_args.kwargs["on_action"]
        from unittest.mock import AsyncMock
        self.prompt.focus = AsyncMock()
        await action("edit", "Вопрос", [], 11)
        before = list(self.messages.controls)
        self.update.side_effect = RuntimeError("disk error")
        self.prompt.value = "Правка"
        await self.send(None)
        self.assertEqual(self.prompt.value, "Правка")
        self.assertEqual(self.messages.controls, before)

    async def test_new_chat_is_blocked_while_generation_runs(self):
        import asyncio
        entered, release = threading.Event(), threading.Event()
        def generate(*a, **kw):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test timeout")
            return "Ответ"
        self.generate.side_effect = generate
        self.prompt.value = "Вопрос"
        job = asyncio.create_task(self.send(None))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            with patch.object(main_ui, "create_new_chat") as create:
                self.menu.call_args.kwargs["on_new_chat_click"](None)
                create.assert_not_called()
        finally:
            release.set()
            await job
        self.save_ai.assert_called_once_with(1, "Ответ")

    async def test_unsaved_reply_can_be_retried_without_duplicate_generation(self):
        self.save_ai.side_effect = [RuntimeError("disk full"), 12]
        self.prompt.value = "Вопрос"
        await self.send(None)
        dialog = self.page.show_dialog.call_args.args[0]
        self.assertEqual(dialog.title.value, "Ответ не сохранён")
        self.assertEqual(len(self.messages.controls), 1)
        retry = dialog.actions[1].on_click
        await retry(None)
        await retry(None)
        self.assertEqual(len(self.messages.controls), 2)
        self.assertEqual(self.save_ai.call_count, 2)
        self.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
