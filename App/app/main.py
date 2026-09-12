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
        load_chat_messages,
        save_ai_message,
        save_user_message,
        seed_demo_chat_if_empty,
        update_message,
    )
except ImportError:
    from services.chat_store import (
        get_or_create_active_chat_id,
        load_chat_messages,
        save_ai_message,
        save_user_message,
        seed_demo_chat_if_empty,
        update_message,
    )
try:
    from ..services.ai import classify_sentiment, reply_for_sentiment
except ImportError:
    from services.ai import classify_sentiment, reply_for_sentiment
try:
    from ..services.llm import DEFAULT_FILENAME, generate_reply, is_model_loaded, list_local_models, load_model
except ImportError:
    from services.llm import DEFAULT_FILENAME, generate_reply, is_model_loaded, list_local_models, load_model


def build_app_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    async def submit_prompt(e):
        await on_send(e)

    prompt = build_prompt(on_submit=submit_prompt)
    selected_files = []
    chat_items = [
        ("Продолжение оформления", "Сегодня · 12 сообщений", True),
        ("Идеи для локального ИИ", "Вчера · 8 сообщений", False),
        ("Материалы проекта Xopilot", "18 февраля · 24 сообщения", False),
        ("Настройка интерфейса", "12 февраля · 16 сообщений", False),
    ]
    workspace_items = [
        ("Xopilot", "Основной проект", ft.Icons.AUTO_AWESOME),
        ("Локальный ИИ", "Модели и эксперименты", ft.Icons.SMART_TOY_OUTLINED),
        ("Дизайн приложения", "Макеты и материалы", ft.Icons.PALETTE_OUTLINED),
    ]
    # editing_message: (message_id или None для ещё не сохранённых в БД сообщений, text, files)
    editing_message = None
    is_sending = False  # защита от повторного Enter/клика, пока предыдущая отправка (вкл. инференс ИИ) ещё идёт
    active_chat_id: int | None = None  # заполняется ниже при загрузке истории из БД
    chat_context = []  # Текстовый контекст Live, включая сообщения текущей сессии без БД.
    chat: ft.Container
    attachment_strip = build_file_attachments(selected_files, lambda _: None)
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

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
        for path in await page.clipboard.get_files():
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
            await page.clipboard.set(text)
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
                    # в БД попадают только структурные quote/reply_to, когда их задаёт сидинг демо-данных.
                message = build_user_message(
                    text,
                    sent_files,
                    on_action=handle_message_action,
                    message_id=new_id,
                )
                chat_context.append({"role": "user", "content": text, "id": new_id})
                # Реверс-список: низ визуала == controls[0], новое сообщение вставляем в начало.
                chat_list.controls.insert(0, message)
                chat_items.insert(0, (text[:32] or "Новый чат", "Только что · 1 сообщение", True))
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

            # Рабочий ИИ: если GGUF-модель положена в App/data/models/ — отвечает она (ленивая загрузка на первое сообщение).
            # Иначе — откат на тестовый ONNX-классификатор тональности (пункт 5 плана).
            # Загрузка/генерация идут в фоновом потоке (asyncio.to_thread) — UI не замирает на время инференса.
            reply_text = None
            try:
                if not is_model_loaded():
                    available = list_local_models()
                    if available:
                        # если лежит несколько файлов -- предпочитаем дефолтный, а не первый по алфавиту
                        chosen = DEFAULT_FILENAME if DEFAULT_FILENAME in available else available[0]
                        await asyncio.to_thread(load_model, chosen)
                if is_model_loaded():
                    reply_text = await asyncio.to_thread(
                        generate_reply, text,
                        history=[dict(item) for item in chat_context[:-1]],
                    )
            except Exception:
                reply_text = None

            if reply_text is None:
                result = classify_sentiment(text)
                if result is not None:
                    label, _score = result
                    reply_text = reply_for_sentiment(label)

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

    # История чата грузится из локальной БД. При первом запуске (пустая БД) сеется демо-диалог
    # напрямую в БД (см. services/chat_store.py) — тестовые сообщения больше не хардкодятся в UI.
    # Если advanced_xopilot ещё не собран (`maturin develop` в Services/) — чат открывается пустым,
    # без падения UI.
    try:
        seed_demo_chat_if_empty()
        active_chat_id = get_or_create_active_chat_id()
        stored_messages = load_chat_messages(active_chat_id)  # [advanced_xopilot.PyMessage, ...]
    except Exception:
        stored_messages = []

    chat_context.extend(
        {"role": msg.role, "content": msg.content, "id": msg.id} for msg in stored_messages
    )

    # Ленивая подгрузка истории: виджетами строим только последние MESSAGE_PAGE_SIZE сообщений,
    # остальные догружаются порциями при прокрутке вверх (см. on_chat_scroll). ListView с
    # build_controls_on_demand и так строит только видимые элементы, но сам список controls
    # держать полным незачем.
    MESSAGE_PAGE_SIZE = 30
    stored_messages.reverse()  # реверс один раз здесь, чтобы ниже не слайсить с конца
    older_messages = stored_messages[MESSAGE_PAGE_SIZE:]
    stored_messages = stored_messages[:MESSAGE_PAGE_SIZE]
    _loading_older = False  # защита от повторной догрузки, пока Flutter не перемерил список

    def _rebuild_files(attachments):
        # attachments: [(name, path), ...] из БД. file_from_path требует реального файла на диске —
        # если файл перенёсли/удалили, вложение тихо пропадает из рендера.
        files = [file_from_path(path) for _name, path in attachments]
        return [f for f in files if f is not None] or None

    chat_messages = [
        build_user_message(
            msg.content,
            files=_rebuild_files(msg.attachments),
            on_action=handle_message_action,
            quote=msg.quote,
            reply_to=msg.reply_to,
            message_id=msg.id,
        )
        if msg.role == "user"
        else build_ai_message(msg.content, on_action=handle_message_action, message_id=msg.id)
        for msg in stored_messages
    ]

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
        chat_list.controls.extend(
            build_user_message(
                msg.content,
                files=_rebuild_files(msg.attachments),
                on_action=handle_message_action,
                quote=msg.quote,
                reply_to=msg.reply_to,
                message_id=msg.id,
            )
            if msg.role == "user"
            else build_ai_message(msg.content, on_action=handle_message_action, message_id=msg.id)
            for msg in batch
        )
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
        voice_button=voice_input.button,
        voice_status=voice_input.status,
        live_button=live.button,
        live_status=live.status,
    )

    async def handle_menu_toggle(e):
        await toggle_menu()

    def open_settings(_):
        page.show_dialog(build_settings_dialog(page, cast(ft.ListView, chat.content), chat_id=active_chat_id))

    def open_account(_):
        page.show_dialog(
            build_settings_dialog(page, cast(ft.ListView, chat.content), start_section=0, chat_id=active_chat_id)
        )

    def open_chats(_):
        page.show_dialog(build_chats_dialog(page, cast(ft.ListView, chat.content), chat_items))

    def open_workspaces(_):
        page.show_dialog(build_workspaces_dialog(page, workspace_items))

    menu = build_menu(
        on_menu_click=handle_menu_toggle,
        on_settings_click=open_settings,
        on_chats_click=open_chats,
        on_workspaces_click=open_workspaces,
        on_account_click=open_account,
    )
    menu_overlay, toggle_menu = build_menu_overlay(
        menu,
        page,
        on_settings_click=open_settings,
        on_chats_click=open_chats,
        on_workspaces_click=open_workspaces,
        on_account_click=open_account,
    )

    # Реверс-список стоит на последнем сообщении сам по себе (индекс 0 == низ),
    # стартовый scroll_to больше не нужен.
    return build_background_layout(chat, prompt_container, menu, menu_overlay)
