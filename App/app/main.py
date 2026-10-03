"""
Файл: /App/app/main.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Окно__
        В котором располагаются элементы интерфейса
"""



import flet as ft
try:
    from .palette import color
except ImportError:
    from app.palette import color
import asyncio
import platform
import threading
from concurrent.futures import CancelledError
from typing import cast

from .backgraund import build_background_layout
from .chat import build_chat
from .material import build_file_attachments, file_from_path
from .message import build_user_message, build_ai_message
from .prompt import build_prompt, build_prompt_container
from .buttons.model import build_model_button
from .buttons.brand import brand_button
from .buttons.send import build_send_button
from .voice_input import VoiceInput
from .live_conversation import LiveConversation
from .menu import build_menu, build_menu_overlay
from .chats import build_chats_dialog
from .workspace_browser import build_workspaces_dialog
from .file_selection import pick_materials
from .palette import install_theme, apply_palette
from .canvas_editor import build_canvas_dialog
try:
    from ..services import workspaces
    from ..services.drafts import read_draft, write_draft
except ImportError:
    from services import workspaces
    from services.drafts import read_draft, write_draft
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
        clear_chat_messages,
        rename_chat,
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
        clear_chat_messages,
        rename_chat,
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
    try:
        from ..services.db import get_setting, get_db
        from ..services.agent import run_agent, LEVELS
    except ImportError:
        from services.db import get_setting, get_db
        from services.agent import run_agent, LEVELS
    try:
        from ..services import chat_store as normal_store, drafts as normal_drafts
        from ..services.material_store import store_material as normal_material
        from ..services.private_chats import PrivateChatSession, PrivateCanvasStore, is_private
    except ImportError:
        from services import chat_store as normal_store, drafts as normal_drafts
        from services.material_store import store_material as normal_material
        from services.private_chats import PrivateChatSession, PrivateCanvasStore, is_private
    private_chats = PrivateChatSession()
    refresh_menu_chats = lambda: None
    load_chat_messages = lambda cid: private_chats.messages(cid) if is_private(cid) else globals()['load_chat_messages'](cid)
    save_user_message = lambda cid, text, **kw: private_chats.add_message(cid, 'user', text, **kw) if is_private(cid) else globals()['save_user_message'](cid, text, **kw)
    save_ai_message = lambda cid, text: private_chats.add_message(cid, 'ai', text) if is_private(cid) else globals()['save_ai_message'](cid, text)
    list_chat_items = lambda: globals()['list_chat_items']() + private_chats.items()
    rename_chat = lambda cid, title: private_chats.rename(cid, title) if is_private(cid) else globals()['rename_chat'](cid, title)
    clear_chat_messages = lambda cid: private_chats.clear(cid) if is_private(cid) else globals()['clear_chat_messages'](cid)
    update_message = lambda mid, text, attachments=None: private_chats.edit_message(mid, text, attachments) if is_private(mid) else globals()['update_message'](mid, text, attachments)
    store_delete_message = lambda mid: private_chats.edit_message(mid, delete=True) if is_private(mid) else globals()['store_delete_message'](mid)
    store_delete_chat = lambda cid: private_chats.delete(cid) if is_private(cid) else globals()['store_delete_chat'](cid)
    read_draft = lambda cid: private_chats.draft(cid) if is_private(cid) else globals()['read_draft'](cid)
    write_draft = lambda cid, text, files: private_chats.draft(cid, text, files) if is_private(cid) else globals()['write_draft'](cid, text, files)

    def material_for_chat(cid):
        if is_private(cid):
            return lambda name, **kwargs: private_chats.store_material(cid, name, **kwargs)
        return normal_material

    def store_chat_material(name, **kwargs):
        return material_for_chat(active_chat_id)(name, **kwargs)

    install_theme(page, get_setting("theme", "light"))
    page.padding = 0
    page.bgcolor = color("#b3f2ff")

    async def submit_prompt(e):
        await on_send(e)

    prompt = build_prompt(on_submit=submit_prompt)
    selected_files = []
    chat_items = []
    # editing_message: (message_id или None для ещё не сохранённых в БД сообщений, text, files)
    editing_message = None
    draft_before_edit = ("", [])
    is_sending = False  # защита от повторного Enter/клика, пока предыдущая отправка (вкл. инференс ИИ) ещё идёт
    request_cancelled = threading.Event()
    failed_request = None
    failed_reason = ""
    active_chat_id: int | None = None  # заполняется ниже при загрузке истории из БД и меняется при переключении/создании/удалении чата
    chat_context = []  # Текстовый контекст Live, включая сообщения текущей сессии без БД.
    chat: ft.Container
    drafts = {}
    title_text = ft.Text("Новый чат", size=16, color=color("#123b43"), weight=ft.FontWeight.W_600,
                         max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    workspace_text = ft.Text("Все чаты", size=11, color=color("#47747a"), max_lines=1,
                             overflow=ft.TextOverflow.ELLIPSIS)
    composer_label = ft.Text("", size=11, color=color("#47747a"), expand=True,
                             max_lines=3, overflow=ft.TextOverflow.ELLIPSIS)
    composer_status = ft.Container(visible=False, content=ft.Row(controls=[composer_label]))
    send_button = build_send_button(submit_prompt)
    empty_state = ft.Container(
        expand=True, alignment=ft.Alignment.CENTER, visible=True,
        padding=ft.Padding.all(24),
        content=ft.Column(
            tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12,
            controls=[ft.Icon(ft.Icons.AUTO_AWESOME, size=40, color=color("#087f8c")),
                      ft.Text("С чего начнём?", size=22, color=color("#123b43"), weight=ft.FontWeight.W_600),
                      ft.Text("Напишите вопрос, прикрепите файл или начните голосовой разговор.",
                              size=13, color=color("#47747a"), text_align=ft.TextAlign.CENTER)],
        ),
    )

    def cancel_edit(_):
        nonlocal editing_message
        if is_sending:
            return
        editing_message = None
        prompt.value, files = draft_before_edit
        selected_files[:] = files
        prompt.update()
        page.run_task(refresh_attachments)
        refresh_composer()

    cancel_edit_button = ft.TextButton(content="Отмена", on_click=cancel_edit, visible=False)
    composer_status.content.controls.append(cancel_edit_button)

    def stop_reply(_):
        request_cancelled.set()
        composer_label.value = "Останавливаю ответ…"
        page.update()

    async def retry_reply(e):
        await on_send(e, retry=True)

    stop_button = ft.TextButton(content="Остановить", on_click=stop_reply, visible=False)
    retry_button = ft.TextButton(content="Повторить", on_click=retry_reply, visible=False)
    composer_status.content.controls.extend([stop_button, retry_button])

    def refresh_composer(update=True):
        send_button.disabled = is_sending
        send_button.opacity = 0.5 if is_sending else 1
        cancel_edit_button.visible = editing_message is not None and not is_sending
        composer_status.visible = is_sending or editing_message is not None or failed_request is not None
        composer_label.value = ("Готовлю ответ…" if is_sending else
                                "Редактирование сообщения" if editing_message is not None else
                                failed_reason or "Ответ не получен")
        composer_label.tooltip = failed_reason if failed_request is not None and not is_sending else None
        stop_button.visible = is_sending
        retry_button.visible = failed_request is not None and not is_sending and editing_message is None
        empty_state.visible = not chat_context
        if update:
            page.update()
    attachment_strip = build_file_attachments(selected_files, lambda _: None)
    file_picker = ft.FilePicker()
    clipboard = ft.Clipboard()
    # Flet 1 auto-registers these once; do not also append to view services.

    async def add_live_message(role, text, attachments=None):
        if active_chat_id is None:
            raise RuntimeError("История недоступна. Откройте или создайте чат перед запуском Live.")
        chat_list = cast(ft.ListView, chat.content)
        if not chat_list.controls:
            chat_context.clear()
        message_id = None
        if active_chat_id is not None:
            save = save_user_message if role == "user" else save_ai_message
            try:
                message_id = await asyncio.to_thread(save, active_chat_id, text,
                    **({"attachments": attachments} if role == "user" and attachments else {}))
            except Exception as exc:
                raise RuntimeError("Не удалось сохранить голосовую реплику в чат.") from exc
        title_text.value = next((t for cid, t, _, _ in list_chat_items() if cid == active_chat_id), title_text.value)
        refresh_menu_chats()
        page.update()
        chat_context.append({"role": role, "content": text, "id": message_id})
        empty_state.visible = False
        build = build_user_message if role == "user" else build_ai_message
        chat_list.controls.insert(0, build(text, on_action=handle_message_action, message_id=message_id,
            **({"files": [file_from_path(path) for _, path in attachments]} if role == "user" and attachments else {})))
        chat_list.update()

    async def add_live_user_message(text, attachments=None):
        await add_live_message("user", text, attachments)

    async def add_live_ai_message(text):
        await add_live_message("ai", text)

    voice_input = VoiceInput(page, prompt, lambda: is_sending or live.busy)
    live = LiveConversation(
        page,
        is_busy=lambda: is_sending or voice_input.busy,
        get_history=lambda: [dict(item) for item in chat_context],
        on_user_message=add_live_user_message,
        on_ai_message=add_live_ai_message,
        get_resources=lambda: ("", []) if is_private(active_chat_id) else workspaces.chat_resources(active_chat_id),
        is_private=lambda: is_private(active_chat_id), material_store=store_chat_material,
        get_material_store=lambda: material_for_chat(active_chat_id),
    )

    async def choose_chat_model(filename: str):
        if is_private(active_chat_id) and filename == 'api':
            page.show_dialog(ft.SnackBar(ft.Text('В анонимном чате доступна только локальная модель.')))
            return False
        try:
            persisted = await asyncio.to_thread(set_selected_chat_model, filename)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось выбрать модель: {exc}")))
            return False
        return True

    model_button, refresh_model_button = build_model_button(on_select=choose_chat_model)
    agent_mode = get_setting('agent_level', 'off')
    agent_button = brand_button(ft.Icons.AUTO_AWESOME_OUTLINED, 'Агентность: выключена')

    def agent_settings(_):
        if is_private(active_chat_id):
            page.show_dialog(ft.SnackBar(ft.Text('В анонимном чате агент не имеет доступа к общей библиотеке.')))
            return
        choice = ft.Dropdown(label='Уровень агентности', value=agent_mode,
            options=[ft.DropdownOption(key='off', text='Выключена'),
                     *[ft.DropdownOption(key=key, text=f'{label} · до {steps} действий' if key != 'auto' else 'Автоматически · по ходу задачи')
                       for key, (label, steps) in LEVELS.items()]])
        feedback = ft.Text('Агент ищет и читает библиотеку, читает и создаёт Canvas. '
                           'Ход работы отображается рядом с кнопкой остановки.', color=color('#47747a'), size=12)
        def save(_):
            nonlocal agent_mode
            try:
                get_db().set_setting('agent_level', choice.value)
                agent_mode = choice.value
                refresh_agent_button()
                page.pop_dialog()
            except Exception as exc:
                feedback.value = str(exc)
            page.update()
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), title=ft.Text('Агентность', color=color('#123b43')),
            content=ft.Column(width=300, tight=True, controls=[choice, feedback]),
            actions=[ft.TextButton(content='Отмена', on_click=lambda _: page.pop_dialog()),
                     ft.FilledButton(content='Применить', on_click=save)]))

    def refresh_agent_button():
        enabled = agent_mode in LEVELS
        agent_button.content.icon = ft.Icons.AUTO_AWESOME if enabled else ft.Icons.AUTO_AWESOME_OUTLINED
        agent_button.border = ft.Border.all(2, ft.Colors.WHITE)
        agent_button.content.size = 22 if enabled else 20
        agent_button.tooltip = 'Агентность: ' + (LEVELS[agent_mode][0] if enabled else 'выключена')
    agent_button.on_click = agent_settings
    refresh_agent_button()

    async def close_voice_modes(e):
        nonlocal editing_message, draft_before_edit, failed_request, failed_reason
        request_cancelled.set()
        persist_draft()
        await asyncio.gather(voice_input.close(e), live.close(e))
        if is_private(active_chat_id):
            private_chats.close_all()
            live.clear_chat()
            if isinstance(page, ft.Page):
                while page.pop_dialog() is not None:
                    pass
            drafts.pop(active_chat_id, None)
            editing_message, draft_before_edit, failed_request = None, ("", []), None
            failed_reason = ""
            selected_files.clear()
            chat_context.clear()
            older_messages.clear()
            prompt.value = ''
            cast(ft.ListView, chat.content).controls.clear()
            # Reconnect restores the ordinary chat, never an unlocked private view.
            cast(ft.ListView, chat.content).controls[:] = _prepare_chat_view(get_or_create_active_chat_id())
            attachment_strip.controls.clear()
            attachment_strip.visible = False
            title_text.value = next((t for cid, t, _, _ in globals()['list_chat_items']() if cid == active_chat_id), 'Новый чат')
        private_chats.close_all()

    async def reconnect_voice_modes(_):
        voice_input.reconnect()
        live.reconnect()
        refresh_composer()

    page.on_disconnect = close_voice_modes
    page.on_connect = reconnect_voice_modes
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
        persist_draft()

    def remove_file(file):
        if file in selected_files:
            selected_files.remove(file)
            page.run_task(refresh_attachments)

    async def on_add_material(_):
        target_id = active_chat_id
        try:
            files = await pick_materials(page, file_picker, store=material_for_chat(target_id))
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось прикрепить файл: {exc}")))
            return
        if target_id != active_chat_id:
            return
        for file in files or []:
            if not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        await refresh_attachments(animated=True)

    async def paste_files():
        if page.web:
            return  # The browser handles ordinary text paste in the field.
        try:
            from ..services.material_store import store_material
        except ImportError:
            from services.material_store import store_material
        target_id = active_chat_id
        store_material = material_for_chat(target_id)
        for path in await clipboard.get_files():
            from pathlib import Path
            managed = await asyncio.to_thread(store_material, Path(path).name, path=path)
            if target_id != active_chat_id:
                return
            file = file_from_path(managed)
            if file and not any(selected.path == file.path for selected in selected_files):
                selected_files.append(file)
        await refresh_attachments(animated=True)

    async def handle_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key.lower() == "v":
            try:
                await paste_files()
            except Exception as exc:
                page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось вставить файлы: {exc}")))

    page.on_keyboard_event = handle_keyboard

    async def handle_message_action(action, text, files, message_id=None):
        nonlocal editing_message, draft_before_edit
        if action in {"edit", "delete"} and (is_sending or live.busy or voice_input.busy):
            page.show_dialog(ft.SnackBar(ft.Text("Дождитесь завершения ответа или голосового ввода.")))
            return
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
            if editing_message is None:
                draft_before_edit = (prompt.value or "", selected_files.copy())
            editing_message = (message_id, text, files or [])
            prompt.value = text
            selected_files[:] = files or []
            page.run_task(refresh_attachments)
            await prompt.focus()
        elif action == "delete":
            if message_id is not None:
                try:
                    if not store_delete_message(message_id):
                        raise RuntimeError("Сообщение не найдено в базе данных.")
                except Exception as exc:
                    page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось удалить сообщение: {exc}")))
                    return
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
            chat_list.update()
        prompt.update()
        refresh_composer()

    async def on_send(e, retry=False):
        nonlocal editing_message, is_sending, failed_request, failed_reason
        if retry and failed_request is None:
            return
        if is_sending or voice_input.busy or live.busy:
            return  # Не отправляем незавершённую диктовку и не дублируем запросы.
        text = failed_request[0] if retry and failed_request else prompt.value or ""
        if not retry and not text.strip() and not selected_files:
            return
        sent_files = selected_files.copy()
        sent_attachments = failed_request[1] if retry and failed_request else [
            (f.name, f.path) for f in sent_files if getattr(f, "path", None)
        ]
        request_chat_id = active_chat_id
        is_sending = True
        request_cancelled.clear()
        refresh_composer()
        try:
            chat_list = cast(ft.ListView, chat.content)
            if not chat_list.controls:
                chat_context.clear()
            should_reply = False

            if retry:
                should_reply = True
            elif editing_message is not None:
                original_id, original_text, original_files = editing_message
                try:
                    if original_id is None or not update_message(original_id, text, sent_attachments):
                        raise RuntimeError("Сообщение не найдено в базе данных.")
                except Exception as exc:
                    page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось сохранить правку: {exc}")))
                    return
                for index, control in enumerate(chat_list.controls):
                    matches = (
                        getattr(control, "data", None) == original_id
                        if original_id is not None
                        else getattr(control, "data", None) == original_text
                    )
                    if matches:
                        chat_list.controls[index] = build_user_message(
                            text,
                            sent_files,
                            on_action=handle_message_action,
                            message_id=original_id,
                        )
                        break
                if failed_request is not None and chat_context and chat_context[-1].get("id") == original_id:
                    failed_request = (text, sent_attachments)
                editing_message = None
                for item in chat_context:
                    if (original_id is not None and item.get("id") == original_id) or (
                        original_id is None and item["role"] == "user" and item["content"] == original_text
                    ):
                        item["content"] = text
                        break
            else:
                try:
                    if request_chat_id is None:
                        raise RuntimeError("База данных недоступна. История не может быть сохранена.")
                    new_id = save_user_message(request_chat_id, text, attachments=sent_attachments)
                except Exception as exc:
                    page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось сохранить сообщение: {exc}")))
                    return
                title_text.value = next((t for cid, t, _, _ in list_chat_items() if cid == request_chat_id), title_text.value)
                refresh_menu_chats()
                empty_state.visible = False
                page.update()
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
            if not retry:
                prompt.value = ""
                selected_files.clear()
                persist_draft()
            prompt.update()
            page.run_task(refresh_attachments)
            chat_list.update()
            # Реверс-список: новое сообщение уже внизу (индекс 0), скролл не нужен.
            await asyncio.sleep(0.08)

            if not should_reply:
                prompt.value, files = draft_before_edit
                selected_files[:] = files
                prompt.update()
                page.run_task(refresh_attachments)
                return

            # Только реальная локальная модель. Выбор хранится отдельно для чата и Live.
            try:
                try:
                    from ..services import api_chat
                except ImportError:
                    from services import api_chat
                private_request = is_private(request_chat_id)
                use_api = api_chat.is_api_selected() and not private_request
                reply_generator = api_chat.generate_reply if use_api else generate_reply
                if not use_api:
                    chosen = get_selected_chat_model()
                    if not chosen:
                        raise RuntimeError("Локальная модель не найдена. Установите её в «Настройки → Модели».")
                    await asyncio.to_thread(ensure_model_loaded, chosen)
                instructions, shared_files = ("", []) if private_request else workspaces.chat_resources(request_chat_id)
                if request_cancelled.is_set():
                    raise CancelledError()
                if agent_mode in LEVELS and not private_request:
                    loop = asyncio.get_running_loop()
                    def progress(value):
                        def refresh():
                            if is_sending:
                                composer_label.value = value
                                page.update()
                        loop.call_soon_threadsafe(refresh)
                    reply_text = await asyncio.to_thread(run_agent, text, chat_id=request_chat_id,
                        history=[dict(item) for item in chat_context[:-1]], attachments=sent_attachments,
                        instructions=instructions, level=agent_mode, cancelled=request_cancelled,
                        on_progress=progress, generate=reply_generator, request_id=chat_context[-1].get('id'))
                else:
                    reply_text = await asyncio.to_thread(
                        reply_generator, text,
                        history=[dict(item) for item in chat_context[:-1]],
                        attachments=[*shared_files, *sent_attachments],
                        instructions=instructions, cancelled=request_cancelled,
                        **({"private": True} if private_request else {}),
                    )
            except (CancelledError, asyncio.CancelledError):
                if request_chat_id != active_chat_id:
                    return
                failed_request = (text, sent_attachments)
                failed_reason = "Генерация остановлена. Вопрос сохранён."
                page.show_dialog(ft.SnackBar(ft.Text("Генерация остановлена. Вопрос сохранён.")))
                return
            except Exception as exc:
                if request_chat_id != active_chat_id:
                    return
                failed_request = (text, sent_attachments)
                failed_reason = f"Не удалось получить ответ ИИ: {exc}"
                page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось получить ответ ИИ: {exc}")))
                return

            if request_chat_id != active_chat_id:
                return
            failed_request = None
            failed_reason = ""

            if reply_text:
                ai_id = None
                try:
                    ai_id = save_ai_message(request_chat_id, reply_text)
                except Exception as exc:
                    recovery_done = False

                    async def retry_save(_):
                        nonlocal recovery_done
                        if recovery_done:
                            return
                        try:
                            recovered_id = save_ai_message(request_chat_id, reply_text)
                        except Exception as retry_error:
                            page.show_dialog(ft.SnackBar(ft.Text(f"Запись не удалась: {retry_error}")))
                            return
                        recovery_done = True
                        if active_chat_id == request_chat_id:
                            chat_list.controls.insert(0, build_ai_message(
                                reply_text, on_action=handle_message_action, message_id=recovered_id,
                            ))
                            chat_context.append({"role": "ai", "content": reply_text, "id": recovered_id})
                            chat_list.update()
                        page.pop_dialog()

                    page.show_dialog(ft.AlertDialog(
                        modal=True,
                        title=ft.Text("Ответ не сохранён"),
                        content=ft.Column(
                            controls=[ft.Text(str(exc)), ft.Text(reply_text, selectable=True)],
                            scroll=ft.ScrollMode.AUTO, width=500, height=400,
                        ),
                        actions=[
                            ft.TextButton(content="Закрыть", on_click=lambda _: page.pop_dialog()),
                            ft.FilledButton(content="Повторить сохранение", on_click=retry_save),
                        ],
                    ))
                    return
                # Реверс-список: ответ ИИ тоже вставляется в начало (низ визуала).
                chat_list.controls.insert(0, build_ai_message(reply_text, on_action=handle_message_action, message_id=ai_id))
                chat_context.append({"role": "ai", "content": reply_text, "id": ai_id})
                chat_list.update()
        finally:
            is_sending = False
            refresh_composer()

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

    def _prepare_chat_view(chat_id: int, stored=None):
        """Загружает историю указанного чата, готовит контекст/пагинацию и возвращает
        список control'ов первой страницы (используется и при старте, и при переключении чата).
        """
        nonlocal active_chat_id, older_messages, failed_request, failed_reason
        failed_reason = ""
        if stored is None:
            stored = load_chat_messages(chat_id)
        workspace_name = (('Временный · удаляется при выходе' if private_chats.temporary(chat_id) else 'Защищённый · пароль · локальная модель')
                          if is_private(chat_id) else workspaces.chat_workspace(chat_id)["name"])
        active_chat_id = chat_id
        workspace_text.value = workspace_name
        agent_button.disabled = is_private(chat_id)
        model_button.disabled = is_private(chat_id)
        refresh_model_button(private=is_private(chat_id))

        empty_state.content.controls[1].value = "С чего начнём?"
        empty_state.content.controls[2].value = "Напишите вопрос, прикрепите файл или начните голосовой разговор."
        try:
            title_text.value = next((title for cid, title, _, _ in list_chat_items()
                                     if cid == chat_id), "Новый чат")
        except Exception:
            title_text.value = "Новый чат"
        empty_state.visible = not stored
        failed_request = ((stored[-1].content, stored[-1].attachments)
                          if stored and stored[-1].role == "user" else None)
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
        chat_messages = _prepare_chat_view(initial_chat_id)
    except Exception as exc:
        initial_chat_id = None
        chat_messages = []
        title_text.value = "История недоступна"
        empty_state.content.controls[1].value = "Не удалось открыть историю"
        empty_state.content.controls[2].value = f"{exc}\nИстория не удалена. Повторите открытие чата после устранения ошибки."
        page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось открыть историю: {exc}")))

    # Ленивая подгрузка истории: виджетами строим только последние MESSAGE_PAGE_SIZE сообщения,
    # остальные догружаются порциями при прокрутке вверх (см. on_chat_scroll). ListView с
    # build_controls_on_demand и так строит только видимые элементы, но самий список controls
    # держать полным незачем.

    def restore_draft(chat_id):
        try:
            saved = read_draft(chat_id)
            return saved.get("text", ""), [f for p in saved.get("files", []) if (f := file_from_path(p))]
        except Exception:
            return "", []

    def persist_draft():
        text, files = ((prompt.value or "", selected_files) if editing_message is None else draft_before_edit)
        try:
            write_draft(active_chat_id, text, [f.path for f in files if f.path])
        except Exception as exc:
            if not getattr(page, "web", False):
                page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось сохранить черновик: {exc}")))

    async def draft_changed(_):
        persist_draft()

    prompt.on_change = draft_changed
    prompt.value, initial_files = restore_draft(initial_chat_id)
    selected_files[:] = initial_files
    attachment_strip.controls = build_file_attachments(selected_files, remove_file).controls
    attachment_strip.visible = bool(selected_files)

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
        send_button=send_button,
        composer_status=composer_status,
        agent_button=agent_button,
    )

    async def handle_menu_toggle(e):
        await toggle_menu()

    def refresh_chat_model_ui(_filename=None):
        refresh_model_button(update=True, private=is_private(active_chat_id))

    def clear_current_history():
        nonlocal failed_request, failed_reason
        if is_sending or live.busy or voice_input.busy:
            raise RuntimeError("Дождитесь завершения ответа или голосового ввода.")
        if active_chat_id is None:
            raise RuntimeError("База данных недоступна.")
        clear_chat_messages(active_chat_id)
        failed_request = None
        failed_reason = ""
        chat_context.clear()
        older_messages.clear()
        cast(ft.ListView, chat.content).controls.clear()
        chat.update()
        refresh_composer()

    def open_settings(_):
        page.show_dialog(
            build_settings_dialog(
                page,
                cast(ft.ListView, chat.content),
                chat_id=active_chat_id,
                on_chat_model_changed=refresh_chat_model_ui,
                on_live_model_changed=live.refresh_model_label,
                on_clear_history=clear_current_history,
                on_select_chat=switch_chat,
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
                on_clear_history=clear_current_history,
                on_select_chat=switch_chat,
            )
        )

    def switch_chat(chat_id: int):
        """Переключает активный чат: перестраивает список сообщений, сбрасывает черновик редактирования."""
        nonlocal editing_message, draft_before_edit, failed_request
        if is_sending or live.busy or voice_input.busy:
            page.show_dialog(ft.SnackBar(ft.Text("Дождитесь завершения ответа или голосового ввода.")))
            return
        if chat_id == active_chat_id:
            return
        if is_private(chat_id) and not private_chats.opened(chat_id):
            password_dialog(chat_id=chat_id)
            return
        if not is_private(active_chat_id):
            drafts[active_chat_id] = (prompt.value or "", selected_files.copy()) if editing_message is None else draft_before_edit
        if not is_private(active_chat_id) or private_chats.opened(active_chat_id):
            persist_draft()
        try:
            stored = load_chat_messages(chat_id)
            # Read all required metadata before changing the active chat.
            if not is_private(chat_id):
                workspaces.chat_workspace(chat_id)
                switch_active_chat(chat_id)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось открыть чат: {exc}")))
            return
        if is_private(active_chat_id):
            private_chats.close(active_chat_id)
            drafts.pop(active_chat_id, None)
        editing_message, draft_before_edit = None, ("", [])
        live.clear_chat()
        chat_list = cast(ft.ListView, chat.content)
        chat_list.controls[:] = _prepare_chat_view(chat_id, stored)
        prompt.value, files = drafts.get(chat_id, restore_draft(chat_id))
        selected_files[:] = files
        page.run_task(refresh_attachments)
        prompt.update()
        refresh_composer()
        chat_list.update()

    def password_dialog(chat_id=None, temporary=False, after_unlock=None):
        if is_sending or live.busy or voice_input.busy:
            page.show_dialog(ft.SnackBar(ft.Text('Сначала завершите ответ или звонок.')))
            return
        password = ft.TextField(label='Отдельный пароль', password=True, can_reveal_password=True, autofocus=True)
        repeat = ft.TextField(label='Повторите пароль', password=True, can_reveal_password=True, visible=chat_id is None)
        feedback = ft.Text('', color=color('#b3261e'), size=12)
        hint = ('Переписка, Canvas и копии вложений исчезнут при выходе из чата.' if temporary else
                'Переписка, Canvas и вложения сохраняются зашифрованными. Пароль восстановить нельзя.')
        hint += '\nТолько локальная модель. Без материалов проектов и статистики профиля.'
        submit = ft.FilledButton(content='Открыть' if chat_id is not None else 'Создать')
        def cancel(_):
            password.value = repeat.value = ''
            page.pop_dialog()
        async def confirm(_):
            if submit.disabled:
                return
            if chat_id is None and password.value != repeat.value:
                feedback.value = 'Пароли не совпадают.'
                page.update()
                return
            submit.disabled = True
            page.update()
            try:
                if chat_id is None:
                    identifier = await asyncio.to_thread(private_chats.create, password.value or '', temporary)
                else:
                    await asyncio.to_thread(private_chats.unlock, chat_id, password.value or '')
                    identifier = chat_id
                password.value = repeat.value = ''
                page.pop_dialog()
                if after_unlock:
                    after_unlock(identifier)
                else:
                    switch_chat(identifier)
            except Exception as exc:
                feedback.value = str(exc)
                submit.disabled = False
                page.update()
        submit.on_click = confirm
        password.on_submit = confirm
        repeat.on_submit = confirm
        dialog = ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text('Открыть защищённый чат' if chat_id is not None else ('Временный анонимный чат' if temporary else 'Защищённый анонимный чат'), color=color('#123b43')),
            content=ft.Column(width=min(430, max(220, (page.width or 800)-112)), tight=True, spacing=16,
                controls=[ft.Text(hint, color=color('#47747a'), size=13), password, repeat, feedback]),
            actions=[ft.TextButton(content='Отмена', on_click=cancel), submit])
        apply_palette(dialog)
        page.show_dialog(dialog)

    def privacy_menu(_):
        if is_sending or live.busy or voice_input.busy:
            page.show_dialog(ft.SnackBar(ft.Text('Сначала завершите ответ или звонок.')))
            return
        def create(temporary):
            page.pop_dialog()
            password_dialog(temporary=temporary)
        def lock(_):
            page.pop_dialog()
            switch_chat(get_or_create_active_chat_id())
        private = is_private(active_chat_id)
        page.show_dialog(ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text('Защищённые чаты', color=color('#123b43')),
            content=ft.Column(width=min(430, max(220, (page.width or 800)-112)), tight=True, spacing=14, controls=[
                ft.Text('Каждый чат защищён отдельным паролем и изолирован от обычной истории. При переключении сохранённый чат блокируется, временный удаляется. Экспорт создаёт обычный файл.', color=color('#47747a'), size=13),
                ft.FilledButton(content='Создать защищённый чат', icon=ft.Icons.LOCK_OUTLINED, on_click=lambda _: create(False)),
                ft.OutlinedButton(content='Создать временный чат', icon=ft.Icons.TIMER_OUTLINED, on_click=lambda _: create(True)),
                *([ft.OutlinedButton(content='Завершить временный чат' if private_chats.temporary(active_chat_id) else 'Закрыть и заблокировать', icon=ft.Icons.LOCK, on_click=lock)] if private else [])]),
            actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())]))

    def start_new_chat(_=None, workspace_id=None):
        """Создаёт новый пустой чат и сразу переключается на него (кнопка «Новый чат» в меню/диалоге чатов)."""
        if is_sending or live.busy or voice_input.busy:
            page.show_dialog(ft.SnackBar(ft.Text("Дождитесь завершения ответа или голосового ввода.")))
            return
        try:
            new_id = create_new_chat()
            workspaces.assign_chat(new_id, workspace_id or workspaces.selected_workspace())
            if workspace_id:
                workspaces.select_workspace(workspace_id)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось создать чат: {exc}")))
            return
        switch_chat(new_id)

    def delete_chat_by_id(chat_id: int):
        """Удаляет чат. Если он был активным — переключается на самый новый из оставшихся,
        а если чатов больше не осталось — создаётся новый.
        """
        if is_sending or live.busy or voice_input.busy:
            page.show_dialog(ft.SnackBar(ft.Text("Дождитесь завершения ответа или голосового ввода.")))
            return
        if is_private(chat_id) and not private_chats.opened(chat_id):
            def unlocked_delete(identifier):
                if delete_chat_by_id(identifier):
                    page.pop_dialog()
                    open_chats(None)
            password_dialog(chat_id=chat_id, after_unlock=unlocked_delete)
            return
        try:
            if not store_delete_chat(chat_id):
                raise RuntimeError("Чат не найден в базе данных.")
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось удалить чат: {exc}")))
            return
        if chat_id == active_chat_id:
            try:
                remaining = [item for item in workspaces.filter_chats(list_chat_items()) if not is_private(item[0])]
            except Exception:
                remaining = []
            if remaining:
                switch_chat(remaining[0][0])
            else:
                start_new_chat()
        return True

    def rename_chat_from_ui(chat_id, title):
        if is_sending or live.busy or voice_input.busy:
            raise RuntimeError("Дождитесь завершения ответа или голосового ввода.")
        title = rename_chat(chat_id, title)
        if chat_id == active_chat_id:
            title_text.value = title
            title_text.update()
        refresh_menu_chats()
        return title

    def move_chat_from_ui(chat_id, identifier):
        if is_sending or live.busy or voice_input.busy:
            raise RuntimeError("Дождитесь завершения ответа или голосового ввода.")
        if is_private(chat_id):
            raise RuntimeError('Анонимный чат изолирован от рабочих пространств.')
        workspaces.assign_chat(chat_id, identifier)
        if chat_id == active_chat_id:
            workspace_text.value = workspaces.chat_workspace(chat_id)["name"]
            page.update()
        return True

    def open_chats(_):
        try:
            chat_items[:] = workspaces.filter_chats(list_chat_items())
        except Exception:
            chat_items.clear()
        page.show_dialog(
            build_chats_dialog(
                page,
                chat_items=chat_items,
                on_select_chat=switch_chat,
                on_create_chat=start_new_chat,
                on_delete_chat=delete_chat_by_id,
                on_rename_chat=rename_chat_from_ui,
                active_chat_id=active_chat_id,
                on_move_chat=move_chat_from_ui,
            )
        )

    def select_workspace_from_ui(identifier):
        if is_sending or live.busy or voice_input.busy:
            raise RuntimeError("Дождитесь завершения ответа или голосового ввода.")
        available = workspaces.filter_chats(list_chat_items(), identifier)
        if available:
            target_id = available[0][0]
        else:
            target_id = create_new_chat()
            workspaces.assign_chat(target_id, identifier)
        switch_chat(target_id)
        workspaces.select_workspace(identifier)
        return True

    def open_workspaces(_):
        try:
            dialog = build_workspaces_dialog(page, on_select=select_workspace_from_ui,
                                            on_changed=lambda: refresh_workspace_title(),
                                            on_open_chat=switch_chat,
                                            on_create_chat=lambda identifier: start_new_chat(workspace_id=identifier))
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось открыть пространства: {exc}")))
            return
        page.show_dialog(dialog)

    async def export_chat(_):
        try:
            from pathlib import Path
            messages = await asyncio.to_thread(load_chat_messages, active_chat_id)
            parts = [f"# {title_text.value}\n"]
            for message in messages:
                parts.append(f"## {'Вы' if message.role == 'user' else 'Zephyr'}\n\n{message.content}\n")
                if message.attachments:
                    parts.append("Вложения: " + ", ".join(name for name, _ in message.attachments) + "\n")
            data = "\n".join(parts).encode("utf-8")
            feedback = ft.Text("Экспорт содержит текст сообщений и названия вложений. Сохранённая копия не защищена паролем чата.", size=12, color=color('#47747a'), selectable=True)

            async def copy_export(_):
                try:
                    await clipboard.set(data.decode('utf-8'))
                    feedback.value = "Текст чата скопирован"
                except Exception as exc:
                    feedback.value = f"Не удалось скопировать: {exc}"
                page.update()

            async def save_export(_):
                save_button.disabled = True
                feedback.value = "Выберите место сохранения" if not page.web else "Готовлю скачивание…"
                page.update()
                try:
                    path = await file_picker.save_file(dialog_title="Экспорт чата", file_name="Xopilot-chat.md", src_bytes=data)
                    if path and not page.web:
                        await asyncio.to_thread(Path(path).write_bytes, data)
                        feedback.value = f"Сохранено: {path}"
                    elif page.web:
                        feedback.value = "Проверьте загрузки браузера. Текст также можно скопировать."
                    else:
                        feedback.value = "Сохранение отменено"
                except Exception as exc:
                    feedback.value = f"Не удалось сохранить: {exc}"
                finally:
                    save_button.disabled = False
                    page.update()

            save_button = ft.FilledButton(content="Сохранить .md", icon=ft.Icons.DOWNLOAD, on_click=save_export)
            async def local_export(_):
                try:
                    try:
                        from ..services.exports import save_local_export
                    except ImportError:
                        from services.exports import save_local_export
                    path = await asyncio.to_thread(save_local_export, 'Xopilot-chat.md', data)
                    feedback.value = f'Локальная копия: {path}'
                except Exception as exc:
                    feedback.value = f'Не удалось сохранить копию: {exc}'
                page.update()
            import os
            local_button = ft.TextButton(content='Локальная копия', icon=ft.Icons.SAVE_ALT, on_click=local_export,
                visible=not page.web or os.environ.get('XOPILOT_LOCAL_WEB') == '1')
            width = max(220, min(600, page.width - 112)) if isinstance(page.width, (int, float)) else 600
            height = max(200, min(400, page.height - 220)) if isinstance(page.height, (int, float)) else 400
            page.show_dialog(ft.AlertDialog(
                bgcolor=color('#eafffa'), title=ft.Text('Экспорт чата', color=color('#123b43')),
                content=ft.Column(width=width, height=height, controls=[feedback,
                    ft.ListView(expand=True, controls=[ft.Text(data.decode('utf-8'), selectable=True, color=color('#123b43'))])]),
                actions=[ft.TextButton(content="Закрыть", on_click=lambda _: page.pop_dialog()),
                         ft.TextButton(content="Копировать", icon=ft.Icons.COPY, on_click=copy_export), local_button, save_button],
            ))
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Не удалось экспортировать чат: {exc}")))

    def refresh_workspace_title():
        if not is_private(active_chat_id):
            workspace_text.value = workspaces.chat_workspace(active_chat_id)["name"]
        page.update()

    def attach_canvas(path):
        if is_sending or live.busy or voice_input.busy:
            raise RuntimeError('Дождитесь завершения ответа или голосового ввода')
        file = file_from_path(path)
        if file is None:
            raise RuntimeError('Не удалось прочитать Canvas')
        selected_files.append(file)
        persist_draft()
        page.run_task(refresh_attachments)

    def open_canvas(_):
        if active_chat_id is None:
            page.show_dialog(ft.SnackBar(ft.Text('Сначала откройте чат')))
            return
        try:
            protected = is_private(active_chat_id)
            page.show_dialog(build_canvas_dialog(page, active_chat_id,
                'all' if protected else workspaces.chat_workspace(active_chat_id)['id'], on_attach=attach_canvas,
                document_store=PrivateCanvasStore(private_chats, active_chat_id) if protected else None,
                material_store=material_for_chat(active_chat_id),
                storage_label=('Только до выхода из временного чата' if private_chats.temporary(active_chat_id)
                    else 'Зашифровано отдельным паролем') if protected else 'Сохранено на устройстве'))
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f'Не удалось открыть Canvas: {exc}')))

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
        get_chat_items=lambda: workspaces.filter_chats(globals()['list_chat_items']()) + private_chats.items(),
        on_select_chat=switch_chat,
        get_active_chat_id=lambda: active_chat_id,
    )

    refresh_menu_chats = getattr(menu_overlay, '_xopilot_refresh_chats', lambda: None)

    # Реверс-список стоит на последнем сообщении сам по себе (индекс 0 == низ),
    # стартовый scroll_to больше не нужен.
    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        border=ft.Border.only(bottom=ft.BorderSide(1, color("#b9eee4"))),
        content=ft.Row(controls=[
            ft.Column(expand=True, tight=True, spacing=2, controls=[title_text, workspace_text]),
            brand_button(ft.Icons.ADD_COMMENT_OUTLINED, "Новый чат", start_new_chat, size=36),
            brand_button(ft.Icons.FORUM_OUTLINED, "Все чаты", open_chats, size=36),
            brand_button(ft.Icons.DOWNLOAD_OUTLINED, "Экспортировать чат", export_chat, size=36),
            brand_button(ft.Icons.DRAW_OUTLINED, "Canvas", open_canvas, size=36),
            brand_button(ft.Icons.LOCK_OUTLINED, "Защищённые чаты", privacy_menu, size=36),
        ]),
    )
    refresh_composer(update=False)
    return apply_palette(build_background_layout(chat, prompt_container, menu, menu_overlay,
                                   header=header, empty_state=empty_state))
