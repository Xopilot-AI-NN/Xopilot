"""Mobile layout, SAF attachments, app-private paths and platform DB keys."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
import flet as ft
from App.services import platforms, paths, db, mobile_runtime, mobile_litert, runtime
from App.app.materials.file_selection import pick_materials
from App.app.theme.background import build_background_layout
from App.app.chat.composer.prompt import build_prompt, build_prompt_container
from App.app.chat.composer.buttons.model import build_model_button


class AndroidPackagingTests(unittest.TestCase):
    def test_cli_exclusions_preserve_private_data_and_expand_host_native_globs(self):
        from scripts import build_android
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = root/'App'
            app.mkdir()
            (app/'advanced_xopilot.host.so').touch()
            (root/'pyproject.toml').write_text(
                '[tool.flet.app]\nexclude=["data", "native", "build"]\n'
                '[tool.flet.android.app]\nexclude=["advanced_xopilot*.so", "assets/models/sentiment.onnx"]\n')
            with patch.object(build_android, 'ROOT', root):
                exclusions = build_android.android_exclusions()
            self.assertTrue({'data', 'native', 'build', 'assets/models/sentiment.onnx',
                             'advanced_xopilot.host.so'} <= set(exclusions))
            self.assertNotIn('advanced_xopilot*.so', exclusions)


class MobileLayoutTests(unittest.TestCase):
    def test_android_canvas_exports_through_saf_without_writing_content_uri(self):
        from App.app.canvas.canvas_editor import build_canvas_dialog
        page = Mock(width=360, height=720, web=False)
        store = Mock()
        document = {'id': 'canvas-test', 'title': 'Test', 'kind': 'text', 'content': 'bytes', 'strokes': []}
        store.list_documents.return_value = [document]
        store.save_document.return_value = document
        store.export_document.return_value = ('test.txt', b'bytes')
        picker = Mock(save_file=AsyncMock(return_value='content://documents/test'))
        with patch('App.app.canvas.canvas_editor.is_android', return_value=True), patch('flet.FilePicker', return_value=picker):
            dialog = build_canvas_dialog(page, 1, document_store=store, on_attach=Mock())
        self.assertEqual(len(dialog.actions), 2)
        with patch('App.app.canvas.canvas_editor.is_android', return_value=True), \
             patch('App.services.mobile_documents.save_document', AsyncMock(return_value=True)) as save, \
             patch('pathlib.Path.write_bytes') as write:
            asyncio.run(dialog.actions[0].on_click(None))
        write.assert_not_called()
        picker.save_file.assert_not_awaited()
        save.assert_awaited_once_with('test.txt', b'bytes')

    def test_composer_resize_keeps_draft_recording_and_action_callbacks(self):
        prompt = build_prompt()
        prompt.value = 'Не потерять черновик при повороте'
        send, microphone, live = [ft.Container(width=40, height=40, border_radius=20,
            on_click=Mock()) for _ in range(3)]
        microphone.disabled = True
        model = ft.Container(expand=True)
        agent = ft.Container(width=60)
        card = build_prompt_container(prompt, Mock(), model_button=model,
            voice_button=microphone, live_button=live, send_button=send, compact=True, viewport_width=393)
        input_row, tools = card.content.controls
        mobile_row = tools.content
        self.assertEqual(input_row.controls, [prompt])
        # Width available after the screen gutters, padding and border. The
        # selector flexes into the remainder, rather than forcing a third row.
        fixed = sum(c.width or 0 for c in mobile_row.controls if c.visible)
        for width in (320, 393):
            self.assertGreaterEqual(width - 16 - 18 - fixed - 2*4, 60)
        click = send.on_click
        card._xopilot_set_compact(True, 320)
        self.assertIs(tools.content, mobile_row)  # Keyboard resize doesn't rebuild controls.
        card._xopilot_set_compact(False, 851)
        self.assertEqual(input_row.controls, [prompt])
        self.assertEqual(send.width, 40)
        card._xopilot_set_compact(True, 393)
        self.assertEqual(prompt.value, 'Не потерять черновик при повороте')
        self.assertTrue(microphone.disabled)
        self.assertIs(send.on_click, click)
        self.assertEqual(tools.content.controls.count(send), 1)
        self.assertNotIn(send, input_row.controls)
        self.assertTrue(send.visible)
        self.assertFalse(live.visible)
        card._xopilot_set_short_input(True)
        self.assertTrue(input_row.visible)
        self.assertEqual(input_row.controls, [prompt])
        self.assertEqual(prompt.height, 28)
        card._xopilot_set_compact(False, 1366)
        self.assertTrue(input_row.visible)
        self.assertEqual(input_row.controls, [prompt])
        card._xopilot_set_compact(True, 393)
        self.assertTrue(input_row.visible)
        self.assertNotIn(prompt, tools.content.controls)

    def test_model_name_is_short_only_on_narrow_phones_and_restores_on_desktop(self):
        with patch('App.app.chat.composer.buttons.model.get_selected_chat_model', return_value='gemma-4-E2B-it.litertlm'), \
                patch('App.app.chat.composer.buttons.model.model_display_name', return_value='Gemma4-e2b'), \
                patch('App.app.chat.composer.buttons.model.api_chat.is_api_selected', return_value=False), \
                patch('App.app.chat.composer.buttons.model.get_loaded_model', return_value=None), \
                patch('App.app.chat.composer.buttons.model.execution_info', return_value={'backend': None}):
            button, refresh = build_model_button()
            button._xopilot_set_compact(True)
            button._xopilot_set_narrow(True)
            label = button.content.controls[1]
            self.assertEqual(label.value, 'e2b')
            self.assertIn('Gemma4-e2b', button.tooltip)
            refresh()
            self.assertEqual(label.value, 'e2b')
            button._xopilot_set_narrow(False)
            button._xopilot_set_compact(False)
            self.assertEqual(label.value, 'Gemma4-e2b')
            self.assertTrue(button.content.controls[0].visible)
            self.assertIsNone(button.expand)

    def test_android_tls_has_real_trusted_ca_certificates_without_disabling_validation(self):
        import os
        import ssl
        with patch.object(runtime, 'is_android', return_value=True), patch.dict(os.environ):
            os.environ.pop('SSL_CERT_FILE', None)
            runtime.configure_android_tls()
            context = ssl.create_default_context(cafile=os.environ['SSL_CERT_FILE'])
            self.assertGreater(context.cert_store_stats()['x509_ca'], 0)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)

    def test_live_overlay_stays_above_chat_without_replacing_composer(self):
        chat, composer, rail = ft.Container(), ft.Container(), ft.Container()
        menu_overlay, call_overlay = ft.Container(), ft.Container(visible=False)
        layout = build_background_layout(chat, composer, rail, menu_overlay,
                                         compact=True, call_overlay=call_overlay)
        self.assertIs(layout.content.controls[-1], call_overlay)
        chat_row = layout.content.controls[0]
        main_column = chat_row.controls[1].content
        input_area = main_column.controls[-1].content
        self.assertIs(input_area.content, composer)
        call_overlay.visible = True
        layout._xopilot_set_compact(False)
        self.assertIs(layout.content.controls[0], chat_row)
        self.assertIs(input_area.content, composer)
        self.assertIs(layout.content.controls[-1], call_overlay)

    def test_portrait_landscape_and_chromebook_resize_restore_menu(self):
        rail = ft.Container(width=76)
        layout = build_background_layout(ft.Container(), ft.Container(), rail, compact=True)
        self.assertFalse(rail.visible)
        for width in (393, 851, 480, 1366):
            layout._xopilot_set_compact(platforms.compact_layout(width))
            self.assertEqual(rail.visible, width >= 600)

    def test_nested_account_form_fits_phone_then_restores_desktop_width(self):
        page = SimpleNamespace(width=393, height=851)
        form = ft.Column(width=500, height=900, controls=[ft.TextField(width=380)])
        dialog = ft.AlertDialog(content=form)
        platforms.fit_dialog(page, dialog)
        self.assertLessEqual(form.width, page.width - 80)
        self.assertLessEqual(form.controls[0].width, form.width)
        self.assertLessEqual(form.height, page.height - 120)
        page.width, page.height = 1366, 1080
        platforms.fit_dialog(page, dialog)
        self.assertEqual(form.width, 500)
        self.assertEqual(form.controls[0].width, 380)
        self.assertEqual(form.height, 900)

    def test_settings_shell_uses_phone_width_without_double_dialog_gutters(self):
        page = SimpleNamespace(width=400, height=851)
        dialog = ft.AlertDialog(content=ft.Column(width=750, height=900),
                                content_padding=ft.Padding.all(0))
        dialog.__dict__['_xopilot_full_width'] = True
        platforms.fit_dialog(page, dialog)
        self.assertEqual(dialog.content.width, 376)
        self.assertEqual(dialog.content.height, 803)

    def test_android_storage_never_moves_to_shared_or_runtime_folder(self):
        with TemporaryDirectory() as folder, patch.object(paths, 'is_android', return_value=True), \
                patch.object(paths, '_ANDROID_DATA_ROOT', folder), \
                patch.dict('os.environ', {'FLET_APP_STORAGE_DATA': folder + '/Xopilot/runtime'}):
            self.assertEqual(paths.app_data_dir(), Path(folder)/'Xopilot')
            self.assertEqual(paths.app_data_dir(), Path(folder)/'Xopilot')
        with patch.object(paths, 'is_android', return_value=True), patch.object(paths, '_ANDROID_DATA_ROOT', None):
            with self.assertRaisesRegex(RuntimeError, 'закрытый каталог'): paths.app_data_dir()


class AndroidDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def test_content_uri_uses_bytes_and_persists_managed_copy(self):
        page=SimpleNamespace(web=False, platform=ft.PagePlatform.ANDROID)
        picker=SimpleNamespace(pick_files=AsyncMock(return_value=[
            SimpleNamespace(name='memo.txt', path='content://documents/42', bytes=b'phone material')]))
        with TemporaryDirectory() as folder:
            def store(name, *, path, data):
                self.assertIsNone(path)
                saved=Path(folder)/name; saved.write_bytes(data); return saved
            files=await pick_materials(page,picker,store=store)
            self.assertFalse(picker.pick_files.call_args.kwargs['with_data'])
            self.assertEqual(Path(files[0].path).read_bytes(), b'phone material')

    async def test_android_cached_document_is_copied_by_path_without_loading_bytes(self):
        page = SimpleNamespace(web=False, platform=ft.PagePlatform.ANDROID)
        with TemporaryDirectory() as folder:
            source = Path(folder)/'cached.txt'
            source.write_text('A document from Android SAF')
            picker = SimpleNamespace(pick_files=AsyncMock(return_value=[
                SimpleNamespace(name=source.name, path=str(source), bytes=None)]))
            store = Mock(return_value=source)
            files = await pick_materials(page, picker, store=store)
            store.assert_called_once_with(source.name, path=str(source), data=None)
            self.assertFalse(picker.pick_files.call_args.kwargs['with_data'])
            self.assertEqual(len(files), 1)

    async def test_inaccessible_uri_reports_failure_without_creating_empty_material(self):
        page=SimpleNamespace(web=False,platform=ft.PagePlatform.ANDROID)
        picker=SimpleNamespace(pick_files=AsyncMock(return_value=[
            SimpleNamespace(name='memo.txt',path='content://documents/42',bytes=None)]))
        store=Mock()
        with self.assertRaisesRegex(RuntimeError,'содержимое'):
            await pick_materials(page,picker,store=store)
        store.assert_not_called()

    async def test_bridge_never_blocks_the_ui_loop_but_worker_can_call_it(self):
        service=SimpleNamespace(call=AsyncMock(return_value='reply'))
        with patch.multiple(mobile_runtime,_service=service,_loop=asyncio.get_running_loop(),
                            _loop_thread=__import__('threading').get_ident()):
            with self.assertRaisesRegex(RuntimeError,'рабочем потоке'): mobile_runtime.call('send')
            self.assertEqual(await asyncio.to_thread(mobile_runtime.call,'send',{'content':'real request'}),'reply')


@unittest.skipIf(db.advanced_xopilot is None, 'Native database not built')
class MobilePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_refresh_updates_chat_and_remote_deletion_preserves_typed_draft(self):
        import json
        from App.app import main as main_ui
        from App.services import chat_store
        page=Mock(width=393,height=851,web=True,services=[],_dialogs=Mock(controls=[]))
        with TemporaryDirectory() as folder, db.advanced_xopilot.PyDatabase(str(Path(folder)/'phone.db'),key='d4'*32) as native:
            with patch.object(db,'_db',native),patch.object(chat_store,'_active_chat_id',None), \
                    patch.object(main_ui,'install_theme'),patch.object(main_ui,'get_selected_chat_model',return_value=None):
                ui=main_ui.build_app_ui(page)
                frame=ui.content.content.controls[0].controls[-1].content
                header,messages,composer=frame.controls
                visual_background,chat,empty=messages.controls
                card=composer.content.content
                prompt=card.content.controls[-2].controls[0]
                old=chat_store.get_or_create_active_chat_id()
                native.rename_chat(old,'Название с ПК');native.add_message(old,'ai','Сообщение с ПК')
                page._xopilot_sync_refresh()
                self.assertFalse(empty.visible)
                self.assertEqual(chat.content.scroll,ft.ScrollMode.AUTO)
                self.assertEqual(header.content.controls[1].controls[0].value,'Название с ПК')
                prompt.value='Черновик, который нельзя потерять'
                native.delete_chat(old)
                remaining=native.create_chat('Другой чат');native.add_message(remaining,'ai','Другой разговор')
                page._xopilot_sync_refresh()
                new=chat_store.get_or_create_active_chat_id()
                self.assertNotIn(new,(old,remaining))
                self.assertEqual(prompt.value,'Черновик, который нельзя потерять')
                self.assertEqual(json.loads(native.get_setting(f'draft:{new}'))['text'],prompt.value)
                self.assertTrue(empty.visible)

    async def test_complete_page_start_rotate_and_send_first_message_to_empty_chat(self):
        from App.app import main as main_ui
        from App.services import chat_store
        page = Mock(width=393, height=851, web=True, services=[], _dialogs=Mock(controls=[]))
        async def settle_layout():
            # Android delivers intermediate metrics before the final keyboard frame.
            for _ in range(2):
                call=page.run_task.call_args
                if call and getattr(call.args[0],'__name__','') in ('settled','settled_layout'):
                    await call.args[0](*call.args[1:])
        with TemporaryDirectory() as folder, db.advanced_xopilot.PyDatabase(str(Path(folder)/'phone.db'),key='d4'*32) as native:
            with patch.object(db, '_db', native), patch.object(chat_store, '_active_chat_id', None), \
                    patch.object(main_ui, 'install_theme'), patch.object(main_ui, 'get_selected_chat_model', return_value=None):
                ui = main_ui.build_app_ui(page)
                background = ui.content
                frame = background.content.controls[0].controls[-1].content
                header, messages, composer = frame.controls
                visual_background, chat, empty = messages.controls
                card = composer.content.content
                prompt = card.content.controls[-2].controls[0]
                prompt.value = 'Первое сообщение с телефона'
                prompt.update = Mock()
                chat.content.update = Mock()
                self.assertTrue(empty.visible)
                self.assertEqual(chat.content.scroll, ft.ScrollMode.HIDDEN)
                tools = card.content.controls[-1].content
                model = tools.controls[1]
                await model.on_click(SimpleNamespace(page=page))
                dialog = page.show_dialog.call_args.args[0]
                level = dialog.content.controls[1]
                level.value = 'high'
                model.update = Mock()
                level.on_select(None)
                self.assertEqual(native.get_setting('agent_level'), 'high')
                send, live = tools.controls[-1], tools.controls[-2]
                self.assertFalse(send.visible)
                self.assertTrue(live.visible)
                with patch.object(ft.Container,'update'):
                    await prompt.on_change(None)
                    self.assertTrue(send.visible)
                    self.assertFalse(live.visible)
                    for width, height in ((320, 640), (393, 425), (851, 393), (1366, 900), (393, 851)):
                        page.width, page.height = width, height
                        page.on_resize(None)
                        self.assertEqual(prompt.value, 'Первое сообщение с телефона')
                        self.assertEqual(len(header.content.controls),3 if width<600 else 6)
                        self.assertIn('Агентность: высокая', model.tooltip)
                    # Flet's Android keyboard changes media insets without changing
                    # page.height or firing on_resize. Exercise that real event.
                    with patch.object(main_ui, 'is_android', return_value=True), \
                            patch.object(platforms, 'is_android', return_value=True):
                        page.width, page.height = 720, 360
                        page.media = SimpleNamespace(view_insets=ft.Padding.only(bottom=190))
                        page.on_media_change(page.media)
                        await settle_layout()
                        self.assertEqual(header.height, 0)
                        self.assertEqual(prompt.max_lines, 1)
                        self.assertEqual(prompt.value, 'Первое сообщение с телефона')
                        self.assertTrue(send.visible)
                        page.media.view_insets = ft.Padding.all(0)
                        page.on_media_change(page.media)
                        await settle_layout()
                        self.assertIsNone(header.height)
                        self.assertEqual(prompt.max_lines, 4)
                        self.assertEqual(prompt.value, 'Первое сообщение с телефона')
                        # A native metrics event must also work when Scaffold's
                        # PageMedia reports zero keyboard insets.
                        service = Mock()
                        with patch.object(mobile_runtime, '_service', service):
                            mobile_runtime.bind_viewport(page, page.on_resize)
                            service.on_metrics(SimpleNamespace(data={'height': 97, 'keyboard': 263}))
                            await settle_layout()
                            self.assertEqual(header.height, 0)
                            self.assertEqual(prompt.max_lines, 1)
                            self.assertTrue(card.content.controls[-2].visible)
                            self.assertEqual(prompt.height, 28)
                            self.assertNotIn(prompt, card.content.controls[-1].content.controls)
                            service.on_metrics(SimpleNamespace(data={'height': 360, 'keyboard': 0}))
                            await settle_layout()
                            self.assertIsNone(header.height)
                            self.assertTrue(card.content.controls[-2].visible)
                            self.assertNotIn(prompt, card.content.controls[-1].content.controls)
                            self.assertEqual(prompt.value, 'Первое сообщение с телефона')
                    await send.on_click(None)
                    self.assertTrue(chat.visible)
                    self.assertFalse(empty.visible)
                    self.assertEqual(chat.content.scroll, ft.ScrollMode.AUTO)
                    rows = native.get_messages(native.list_chats()[0][0])
                    self.assertEqual([(r.role, r.content) for r in rows], [('user', 'Первое сообщение с телефона')])
                    self.assertEqual(prompt.value, '')


@unittest.skipIf(db.advanced_xopilot is None, 'Native database not built')
class MobileKeyDatabaseTests(unittest.TestCase):
    def test_explicit_random_key_survives_reopen_wrong_key_cannot_read_history(self):
        with TemporaryDirectory() as folder:
            database=Path(folder)/'mobile.db'
            key='a9'*32
            native=db.advanced_xopilot.PyDatabase(str(database),key=key)
            chat=native.create_chat('На телефоне'); native.add_message(chat,'user','Private phone message')
            native.close(); del native
            self.assertNotIn(b'Private phone message',database.read_bytes())
            with self.assertRaises(RuntimeError): db.advanced_xopilot.PyDatabase(str(database),key='b8'*32)
            native=db.advanced_xopilot.PyDatabase(str(database),key=key)
            self.assertEqual(native.get_messages(chat)[0].content,'Private phone message')
            native.close(); del native
            with self.assertRaises(RuntimeError): db.advanced_xopilot.PyDatabase(str(database),key='invalid')

    def test_android_does_not_open_database_before_keystore_ready(self):
        with patch.object(db,'_db',None),patch.object(db,'_mobile_key',None), \
                patch.object(platforms,'is_android',return_value=True),patch.object(db,'_app_data_dir',return_value='/unused'):
            with self.assertRaisesRegex(RuntimeError,'Keystore'): db.get_db()

    def test_reconnect_accepts_same_key_but_cannot_replace_open_database_key(self):
        with patch.object(db, '_db', object()), patch.object(db, '_mobile_key', 'a9'*32):
            db.configure_mobile_key('A9'*32)
            with self.assertRaisesRegex(RuntimeError, 'заменить ключ'):
                db.configure_mobile_key('b8'*32)
            self.assertEqual(db._mobile_key, 'a9'*32)


class LazyMobileCapabilitiesTests(unittest.IsolatedAsyncioTestCase):
    async def test_home_restores_cache_without_loading_native_model_library(self):
        import json
        with TemporaryDirectory() as folder:
            model = Path(folder)/'local.litertlm'
            model.write_bytes(b'model fixture')
            settings = {}
            database = SimpleNamespace(get_setting=lambda key: settings.get(key),
                                       set_setting=lambda key, value: settings.update({key: value}))
            service = SimpleNamespace(call=AsyncMock(return_value={'audio': True, 'vision': False}))
            with patch.object(db, 'get_db', return_value=database), \
                 patch('App.services.llm.list_local_models', return_value=[model.name]), \
                 patch('App.services.llm.get_model_path', return_value=str(model)), \
                 patch.multiple(mobile_runtime, _service=service, _capabilities={}):
                await mobile_runtime.refresh_capabilities(inspect_missing=False)
                service.call.assert_not_awaited()
                self.assertEqual(mobile_runtime._capabilities, {})
                await mobile_runtime.refresh_capabilities()
                service.call.assert_awaited_once_with('capabilities', {'path': str(model)})
                self.assertIn(str(model), json.loads(settings['mobile_model_capabilities_v1']))
                mobile_runtime._capabilities.clear()
                service.call.reset_mock()
                await mobile_runtime.refresh_capabilities(inspect_missing=False)
                service.call.assert_not_awaited()
                self.assertEqual(mobile_runtime.capabilities(model), {'audio': True, 'vision': False})
                model.write_bytes(b'new different model fixture')
                mobile_runtime._capabilities.clear()
                await mobile_runtime.refresh_capabilities(inspect_missing=False)
                self.assertEqual(mobile_runtime._capabilities, {})
                service.call.assert_not_awaited()


if __name__ == '__main__': unittest.main()
