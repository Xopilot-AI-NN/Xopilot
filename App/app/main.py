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
    from ..services.llm import generate_reply, is_model_loaded, list_local_models, load_model
except ImportError:
    from services.llm import generate_reply, is_model_loaded, list_local_models, load_model


def build_app_ui(page: ft.Page) -> ft.Control:
    page.padding = 0
    page.bgcolor = "#b3f2ff"

    prompt = build_prompt()
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
    attachment_strip = build_file_attachments(selected_files, lambda _: None)
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

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
        elif e.key.lower() == "enter" and not e.shift:
            await on_send(e)

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
        if is_sending:
            return  # уже идёт отправка (напр., генерация ИИ) — игнорируем повторный Enter/клик, чтобы не дублировать
        text = prompt.value or ""
        if not text.strip() and not selected_files:
            return
        is_sending = True
        try:
            chat_list = cast(ft.ListView, chat.content)
            sent_files = selected_files.copy()
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
                chat_list.controls.append(message)
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
            await asyncio.sleep(0.08)
            await chat_list.scroll_to(offset=-1, duration=250)

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
                        await asyncio.to_thread(load_model, available[0])
                if is_model_loaded():
                    reply_text = await asyncio.to_thread(generate_reply, text)
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
                chat_list.controls.append(
                    build_ai_message(reply_text, on_action=handle_message_action, message_id=ai_id)
                )
                chat_list.update()
                await chat_list.scroll_to(offset=-1, duration=200)
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
    chat = build_chat(chat_messages)
    prompt_container = build_prompt_container(
        prompt,
        on_send,
        on_add_material=on_add_material,
        attachments=attachment_strip,
    )

    async def handle_menu_toggle(e):
        await toggle_menu()

    def open_settings(_):
        page.show_dialog(build_settings_dialog(page, cast(ft.ListView, chat.content)))

    def open_account(_):
        page.show_dialog(
            build_settings_dialog(page, cast(ft.ListView, chat.content), start_section=0)
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

    async def scroll_chat_to_bottom():
        await asyncio.sleep(0.15)
        await cast(ft.ListView, chat.content).scroll_to(offset=-1)

    page.run_task(scroll_chat_to_bottom)

    return build_background_layout(chat, prompt_container, menu, menu_overlay)