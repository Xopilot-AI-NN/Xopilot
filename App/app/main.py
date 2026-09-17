"""
Файл: /App/app/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Окно__
        В котором располагаются элементы интерфейса
"""



import flet as ft
import asyncio
import platform
from typing import cast

from .backgraund import build_background_layout
from .chat import build_chat
from .material import build_file_attachments, file_from_path
from .message import build_user_message, build_ai_message
from .prompt import build_prompt, build_prompt_container
from .buttons.model import build_model_button
from .voice_input import VoiceInput
from .live_conversation import LiveConversation
from .menu import build_menu, build_menu_overlay
from .chats import build_chats_dialog
from .workspace_browser import build_workspaces_dialog
try:
    from ..settings.main import build_settings_dialog
except ImportError:
    from settings.main import build_settings_dialog
try:
    from ..services.chat_store import (
        get_or_create_active_chat_id,
        switch_active_chat,
        create_new_chat,
        load_chat_messages,
        save_ai_message,
        save_user_message,
        cleanup_legacy_messages,
        list_chat_items,
        update_message,
        delete_message as store_delete_message,
        delete_chat as store_delete_chat,
    )
except ImportError:
    from services.chat_store import (
        get_or_create_active_chat_id,
        switch_active_chat,
        create_new_chat,
        load_chat_messages,
        save_ai_message,
        save_user_message,
        cleanup_legacy_messages,
        list_chat_items,
        update_message,
        delete_message as store_delete_message,
        delete_chat as store_delete_chat,
    )
try:
    from ..services.llm import ensure_model_loaded, generate_reply
    from ..services.model_settings import (
        get_selected_chat_model, model_display_name, set_selected_chat_model,
    )
except ImportError:
    from services.llm import ensure_model_loaded, generate_reply
    from services.model_settings import (
        get_selected_chat_model, model_display_name, set_selected_chat_model,
    )


def build_app_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    async def submit_prompt(e):
        await on_send(e)

    prompt = build_prompt(on_submit=submit_prompt)
    selected_files = []
    chat_items = []
    workspace_items = [
        ("Xopilot", "Основной проект", ft.Icons.AUTO_AWESOME),
        ("Локальный ИИ", "Модели и эксперименты", ft.Icons.SMART_TOY_OUTLINED),
        ("Дизайн приложения", "Макеты и материалы", ft.Icons.PALETTE_OUTLINED),
    ]
    # editing_message: (message_id или None для ещё не сохранённых в БД сообщений, text, files)
    editing_message = None
    is_sending = False  # защита от повторного Enter/клика, пока предыдущая отправка (вкл. инференс ИИ) ещё идёт
    active_chat_id: int | None = None  # заполняется ниже при загрузке истории из БД и меняется при переключении/создании/удалении чата
    chat_context = []  # Текстовый контекст Live, включая сообщения текущей сессии без БД.
    chat: ft.Container
    attachment_strip = build_file_attachments(selected_files, lambda _: None)
    file_picker = ft.FilePicker()
    clipboard = ft.Clipboard()
    page.services.append(file_picker)
    page.services.append(clipboard)

    async def add_live_message(role, text):
        chat_list = cast(ft.ListView, chat.content)
        if not chat_list.controls:
            chat_context.clear()
        message_id = None
        if active_chat_id is not None:
            save = save_user_message if role == "user" else save_ai_message
            try:
                message_id = await asyncio.to_thread(save, active_chat_id, text)
            except Exception as exc:
                raise RuntimeError("Не удалось сохранить голосовую реплику в чат.") from exc
        chat_context.append({"role": role, "content": text, "id": message_id})
        build = build_user_message if role == "user" else build_ai_message
        chat_list.controls.insert(0, build(text, on_action=handle_message_action, message_id=message_id))
        chat_list.update()

    async def add_live_user_message(text):
        await add_live_message("user", text)

    async def add_live_ai_message(text):
        await add_live_message("ai", text)

    voice_input = VoiceInput(page, prompt, lambda: is_sending or live.busy)
    live = LiveConversation(
        page,
        is_busy=lambda: is_sending or voice_input.busy,
        get_history=lambda: [dict(item) for item in chat_context],
        on_user_message=add_live_user_message,
        on_ai_message=add_live_ai_message,
    )

    async def choose_chat_model(filename: str):
        try:
            persisted = await asyncio.to_thread(set_selected_chat_model, filename)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось выбрать модель: {exc}")))
            return
        suffix = "" if persisted else " · только на эту сессию"
        page.show_dialog(
            ft.SnackBar(ft.Text(f"Модель чата: {model_display_name(filename)}{suffix}"))
        )

    model_button, refresh_model_button = build_model_button(on_select=choose_chat_model)

    async def close_voice_modes(e):
        await asyncio.gather(voice_input.close(e), live.close(e))

    page.on_disconnect = close_voice_modes
    page.on_close = close_voice_modes

    async def refresh_attachments(animated: bool = False):
        rendered = build_file_attachments(selected_files, remove_file)
        attachment_strip.controls = rendered.controls
        attachment_strip.visible = rendered.visible
        if animated and selected_files:
            attachment_strip.opacity = 0
            attachment_strip.update()
            await asyncio.sleep(0.02)
            attachment_strip.opacity = 1
        attachment_strip.update()

    def remove_file(file):
        if file in selected_files:
            selected_files.remove(file)
            page.run_task(refresh_attachments)

    async def on_add_material(_):
        files = await file_picker.pick_files(
            dialog_title="Выберите материалы",
            allow_multiple=True,
            with_data=False,
        )
        for file in files or []:
            if not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        await refresh_attachments(animated=True)

    async def paste_files():
        for path in await clipboard.get_files():
            file = file_from_path(path)
            if file and not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        await refresh_attachments(animated=True)

    async def handle_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key.lower() == "v":
            await paste_files()

    page.on_keyboard_event = handle_keyboard

    async def handle_message_action(action, text, files, message_id=None):
        nonlocal editing_message
        if action == "copy":
            await clipboard.set(text)
        elif action == "reply":
            prompt.value = f"Ответ на сообщение:\n{text}\n\n"
            await prompt.focus()
        elif action == "quote":
            quoted_text = "\n".join(f"> {line}" for line in text.splitlines())
            prompt.value = f"{quoted_text}\n\n"
            await prompt.focus()
        elif action == "edit":
            editing_message = (message_id, text, files or [])
            prompt.value = text
            await prompt.focus()
        elif action == "delete":
            chat_list = cast(ft.ListView, chat.content)
            for index, control in enumerate(chat_list.controls):
                matches = (
                    getattr(control, "data", None) == message_id
                    if message_id is not None
                    else getattr(control, "data", None) == text
                )
                if matches:
                    del chat_list.controls[index]
                    break
            for index, item in enumerate(chat_context):
                if (message_id is not None and item.get("id") == message_id) or (
                    message_id is None and item["content"] == text
                ):
                    del chat_context[index]
                    break
            if editing_message is not None and editing_message[0] == message_id:
                editing_message = None
            if message_id is not None:
                try:
                    store_delete_message(message_id)
                except Exception:
                    pass  # БД недоступна — сообщение всё равно скрыто из UI на эту сессию
            chat_list.update()
        prompt.update()

    async def on_send(e):
        nonlocal editing_message, is_sending
        if is_sending or voice_input.busy or live.busy:
            return  # Не отправляем незавершённую диктовку и не дублируем запросы.
        text = prompt.value or ""
        if not text.strip() and not selected_files:
            return
        sent_files = selected_files.copy()
        prompt.value = ""
        selected_files.clear()
        prompt.update()
        is_sending = True
        try:
            chat_list = cast(ft.ListView, chat.content)
            if not chat_list.controls:
                chat_context.clear()
            should_reply = False

            if editing_message is not None:
                original_id, original_text, original_files = editing_message
                for index, control in enumerate(chat_list.controls):
                    matches = (
                        getattr(control, "data", None) == original_id
                        if original_id is not None
                        else getattr(control, "data", None) == original_text
                    )
                    if matches:
                        chat_list.controls[index] = build_user_message(
                            text,
                            original_files,
                            on_action=handle_message_action,
                            message_id=original_id,
                        )
                        break
                editing_message = None
                for item in chat_context:
                    if (original_id is not None and item.get("id") == original_id) or (
                        original_id is None and item["role"] == "user" and item["content"] == original_text
                    ):
                        item["content"] = text
                        break
                if original_id is not None:
                    try:
                        update_message(original_id, text)
                    except Exception:
                        pass  # БД недоступна — правка останется только в UI на эту сессию
            else:
                new_id = None
                if active_chat_id is not None:
                    try:
                        attachments = [
                            (f.name, f.path) for f in sent_files if getattr(f, "path", None)
                        ]
                        new_id = save_user_message(active_chat_id, text, attachments=attachments)
                    except Exception:
                        pass  # БД недоступна (напр., advanced_xopilot ещё не собран) — сообщение останется только в UI на эту сессию
                    # Цитата/ответ для новых сообщений пока не персистятся отдельно от текста промпта
                    # (они вставляются как обычный текст в handle_message_action, как и до этого) —
                    # структурные поля quote/reply_to уже сохранённых сообщений сохраняются отдельно.
                message = build_user_message(
                    text,
                    sent_files,
                    on_action=handle_message_action,
                    message_id=new_id,
                )
                chat_context.append({"role": "user", "content": text, "id": new_id})
                # Реверс-список: низ визуала == controls[0], новое сообщение вставляем в начало.
                chat_list.controls.insert(0, message)
                should_reply = True

            # Сразу очищаем поле ввода и показываем отправленное сообщение — ДО генерации ответа ИИ.
            # Раньше это делалось после инференса — поле висело непустым на время генерации,
            # из-за чего Enter казался сломанным, а повторные нажатия дублировали отправку.
            prompt.value = ""
            selected_files.clear()
            prompt.update()
            page.run_task(refresh_attachments)
            chat_list.update()
            # Реверс-список: новое сообщение уже внизу (индекс 0), скролл не нужен.
            await asyncio.sleep(0.08)

            if not should_reply:
                return

            # Только реальная локальная модель. Выбор хранится отдельно для чата и Live.
            try:
                chosen = get_selected_chat_model()
                if not chosen:
                    raise RuntimeError("Локальная модель не найдена. Добавьте файл .litertlm в App/data/models/.")
                await asyncio.to_thread(ensure_model_loaded, chosen)
                reply_text = await asyncio.to_thread(
                    generate_reply, text,
                    history=[dict(item) for item in chat_context[:-1]],
                )
            except Exception as exc:
                page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось получить ответ ИИ: {exc}")))
                return

            if reply_text:
                ai_id = None
                if active_chat_id is not None:
                    try:
                        ai_id = save_ai_message(active_chat_id, reply_text)
                    except Exception:
                        pass
                # Реверс-список: ответ ИИ тоже вставляется в начало (низ визуала).
                chat_list.controls.insert(0, build_ai_message(reply_text, on_action=handle_message_action, message_id=ai_id))
                chat_context.append({"role": "ai", "content": reply_text, "id": ai_id})
                chat_list.update()
        finally:
            is_sending = False

    MESSAGE_PAGE_SIZE = 30
    older_messages: list = []  # остаток истории текущего чата, догружается порциями при скролле вверх (см. on_chat_scroll)
    _loading_older = False  # защита от повторной догрузки, пока Flutter не перемерил список

    def _rebuild_files(attachments):
        # attachments: [(name, path), ...] из БД. file_from_path требует реального файла на диске —
        # если файл перенёсли/удалили, вложение тихо пропадает из рендера.
        files = [file_from_path(path) for _name, path in attachments]
        return [f for f in files if f is not None] or None

    def _build_message_control(msg):
        """Один advanced_xopilot.PyMessage -> готовый control для ListView (используется и при первоначальной
        загрузке чата, и при догрузке старых сообщений, и при переключении между чатами)."""
        if msg.role == "user":
            return build_user_message(
                msg.content,
                files=_rebuild_files(msg.attachments),
                on_action=handle_message_action,
                quote=msg.quote,
                reply_to=msg.reply_to,
                message_id=msg.id,
            )
        return build_ai_message(msg.content, on_action=handle_message_action, message_id=msg.id)

    def _prepare_chat_view(chat_id: int):
        """Загружает историю указанного чата, готовит контекст/пагинацию и возвращает
        список control'ов первой страницы (используется и при старте, и при переключении чата).
        """
        nonlocal active_chat_id, older_messages
        try:
            stored = load_chat_messages(chat_id)  # [advanced_xopilot.PyMessage, ...]
        except Exception:
            stored = []
        active_chat_id = chat_id
        chat_context.clear()
        chat_context.extend({"role": msg.role, "content": msg.content, "id": msg.id} for msg in stored)
        # Реверс-список: ленивая подгрузка истории строит только последние MESSAGE_PAGE_SIZE сообщений,
        # остальные догружаются порциями при прокрутке вверх (см. on_chat_scroll).
        stored.reverse()  # реверс один раз здесь, чтобы ниже не слайсить с конца
        older_messages = stored[MESSAGE_PAGE_SIZE:]
        page_messages = stored[:MESSAGE_PAGE_SIZE]
        return [_build_message_control(msg) for msg in page_messages]

    # Удаляем известные старые заглушки один раз. Новая база начинает с пустого чата.
    try:
        cleanup_legacy_messages()
    except Exception as exc:
        page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось очистить старые тестовые сообщения: {exc}")))
    try:
        initial_chat_id = get_or_create_active_chat_id()
    except Exception:
        initial_chat_id = None

    # Ленивая подгрузка истории: виджетами строим только последние MESSAGE_PAGE_SIZE сообщения,
    # остальные догружаются порциями при прокрутке вверх (см. on_chat_scroll). ListView с
    # build_controls_on_demand и так строит только видимые элементы, но самий список controls
    # держать полным незачем.
    chat_messages = _prepare_chat_view(initial_chat_id) if initial_chat_id is not None else []

    async def on_chat_scroll(e: ft.OnScrollEvent):
        """Догрузка старых сообщений при прокрутке вверх.

        В реверс-списке pixels=0 -- низ (новейшие сообщения), а max_scroll_extent --
        верх, где лежат старейшие из загруженных. Дошли почти до верха -- вставляем
        следующую порцию в КОНЕЦ списка controls (визуально -- выше): позиции уже
        отрисованных элементов относительно нижнего якоря не меняются, прыжка нет.
        """
        nonlocal older_messages, _loading_older
        if _loading_older or not older_messages:
            return
        near_top = (
            e.max_scroll_extent <= 0  # контент ещё не скроллится (короткие сообщения) -- добираем, пока не заполнит экран
            or e.pixels >= e.max_scroll_extent - e.viewport_dimension - 48
        )
        if not near_top:
            return
        _loading_older = True
        batch, older_messages = older_messages[:MESSAGE_PAGE_SIZE], older_messages[MESSAGE_PAGE_SIZE:]
        chat_list = cast(ft.ListView, chat.content)
        chat_list.controls.extend(_build_message_control(msg) for msg in batch)
        chat_list.update()
        # пока Dart-сторона не перемерила выросший max_scroll_extent, события скролла
        # ещё рапортуют "почти наверху" -- короткая защита от повторной догрузки
        await asyncio.sleep(0.2)
        _loading_older = False

    chat = build_chat(chat_messages, on_scroll=on_chat_scroll)
    prompt_container = build_prompt_container(
        prompt,
        on_send,
        on_add_material=on_add_material,
        attachments=attachment_strip,
        model_button=model_button,
        voice_button=voice_input.button,
        voice_status=voice_input.status,
        live_button=live.button,
        live_status=live.status,
    )

    async def handle_menu_toggle(e):
        await toggle_menu()

    def refresh_chat_model_ui(_filename=None):
        refresh_model_button(update=True)

    def open_settings(_):
        page.show_dialog(
            build_settings_dialog(
                page,
                cast(ft.ListView, chat.content),
                chat_id=active_chat_id,
                on_chat_model_changed=refresh_chat_model_ui,
                on_live_model_changed=live.refresh_model_label,
            )
        )

    def open_account(_):
        page.show_dialog(
            build_settings_dialog(
                page,
                cast(ft.ListView, chat.content),
                start_section=0,
                chat_id=active_chat_id,
                on_chat_model_changed=refresh_chat_model_ui,
                on_live_model_changed=live.refresh_model_label,
            )
        )

    def switch_chat(chat_id: int):
        """Переключает активный чат: перестраивает список сообщений, сбрасывает черновик редактирования."""
        nonlocal editing_message
        editing_message = None
        chat_list = cast(ft.ListView, chat.content)
        chat_list.controls[:] = _prepare_chat_view(chat_id)
        chat_list.update()
        switch_active_chat(chat_id)

    def start_new_chat(_=None):
        """Создаёт новый пустой чат и сразу переключается на него (кнопка «Новый чат» в меню/диалоге чатов)."""
        try:
            new_id = create_new_chat()
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось создать чат: {exc}")))
            return
        switch_chat(new_id)

    def delete_chat_by_id(chat_id: int):
        """Удаляет чат. Если он был активным — переключается на самый новый из оставшихся,
        а если чатов больше не осталось — создаётся новый.
        """
        try:
            store_delete_chat(chat_id)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось удалить чат: {exc}")))
            return
        if chat_id == active_chat_id:
            try:
                remaining = list_chat_items()
            except Exception:
                remaining = []
            if remaining:
                switch_chat(remaining[0][0])
            else:
                start_new_chat()

    def open_chats(_):
        try:
            chat_items[:] = list_chat_items()
        except Exception:
            chat_items.clear()
        page.show_dialog(
            build_chats_dialog(
                page,
                chat_items=chat_items,
                on_select_chat=switch_chat,
                on_create_chat=start_new_chat,
                on_delete_chat=delete_chat_by_id,
            )
        )

    def open_workspaces(_):
        page.show_dialog(build_workspaces_dialog(page, workspace_items))

    menu = build_menu(
        on_menu_click=handle_menu_toggle,
        on_new_chat_click=start_new_chat,
        on_settings_click=open_settings,
        on_chats_click=open_chats,
        on_workspaces_click=open_workspaces,
        on_account_click=open_account,
    )
    menu_overlay, toggle_menu = build_menu_overlay(
        menu,
        page,
        on_new_chat_click=start_new_chat,
        on_settings_click=open_settings,
        on_chats_click=open_chats,
        on_workspaces_click=open_workspaces,
        on_account_click=open_account,
    )

    # Реверс-список стоит на последнем сообщении сам по себе (индекс 0 == низ),
    # стартовый scroll_to больше не нужен.
    return build_background_layout(chat, prompt_container, menu, menu_overlay)