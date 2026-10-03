"""
Файл: App/app/live_conversation.py
Разработчик: DenBroLiik
Описание: Голосовой режим: слушать реплику, распознать, ответить и озвучить.
    Дополнительно — две кнопки-тумблера (камера/экран): когда один из них включён, перед
    каждым ответом захватывается один кадр и передаётся модели вместе с голосовым вопросом —
    так модель «видит», что происходит в момент реплики.
    UI управляет состояниями и отменой; устройства и модель находятся в services.
"""

import asyncio
import threading
import os
import time
from concurrent.futures import CancelledError

import flet as ft
try:
    from .palette import color
except ImportError:
    from app.palette import color

from .buttons.live import build_live_button
from .buttons.live_camera import build_live_camera_button
from .buttons.live_display import build_live_display_button
from .buttons.brand import brand_button, brand_gradient
from .file_selection import pick_materials
from .material import build_file_attachments
try:
    from ..services.live_audio import check_live_audio, record_utterance
    from ..services.speech_output import SpeechOutput
    from ..services.llm import (
        SpeechNotRecognizedError, generate_live_reply, prepare_voice_model, transcribe_audio, execution_label,
    )
    from ..services.model_settings import get_selected_live_model, model_display_name
    from ..services.live_vision import capture_camera_frame, capture_screen_frame, CameraStream
except ImportError:
    from services.live_audio import check_live_audio, record_utterance
    from services.speech_output import SpeechOutput
    from services.llm import (
        SpeechNotRecognizedError, generate_live_reply, prepare_voice_model, transcribe_audio, execution_label,
    )
    from services.model_settings import get_selected_live_model, model_display_name
    from services.live_vision import capture_camera_frame, capture_screen_frame, CameraStream


class VisionCaptureError(RuntimeError):
    pass


class LiveConversation:
    def __init__(self, page, is_busy, get_history, on_user_message, on_ai_message, get_resources=None, is_private=None, material_store=None, get_material_store=None):
        self.page = page
        self.is_busy = is_busy
        self.get_history = get_history
        self.on_user_message = on_user_message
        self.on_ai_message = on_ai_message
        self.get_resources = get_resources or (lambda: ("", []))
        self.is_private = is_private or (lambda: False)
        self.material_store = material_store
        self.get_material_store = get_material_store or (lambda: self.material_store)
        self.button = build_live_button(on_click=self.open_call)
        self.camera_on = False
        self.screen_on = False
        self.camera_button = build_live_camera_button(on_click=self.toggle_camera)
        self.screen_button = build_live_display_button(on_click=self.toggle_screen)
        self.status_text = ft.Text(size=13, color=color("#47747a"), text_align=ft.TextAlign.CENTER)
        self.state_title = ft.Text("Готов к разговору", size=22, weight=ft.FontWeight.W_600,
                                   color=color("#123b43"), text_align=ft.TextAlign.CENTER)
        self.engine_text = ft.Text(size=11, color=color("#47747a"), text_align=ft.TextAlign.CENTER)
        self.orb = ft.Container(width=72, height=72, border_radius=36, gradient=brand_gradient(),
            border=ft.Border.all(2, ft.Colors.WHITE), alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.GRAPHIC_EQ, color=ft.Colors.WHITE, size=34))
        self.orb._xopilot_fixed_colors = True
        self.interrupt_button = ft.TextButton(
            content="Перебить", style=ft.ButtonStyle(color=color("#087f8c")), on_click=self.interrupt,
        )
        self.end_button = ft.IconButton(
            icon=ft.Icons.CALL_END, icon_color=color("#d9364f"),
            tooltip="Завершить Live", on_click=self.end_call,
        )
        self.microphone_muted = False
        self.mute_button = brand_button(ft.Icons.MIC, "Выключить микрофон", self.toggle_mute, size=46)
        self.mute_label = ft.Text("Микрофон", size=11, color=color("#47747a"))
        self.voice_output_enabled = True
        self.sound_button = brand_button(ft.Icons.VOLUME_UP, "Выключить озвучивание", self.toggle_sound, size=46)
        self.sound_label = ft.Text("Звук", size=11, color=color("#47747a"))
        self.preview = ft.Image(src=b"", height=200, fit=ft.BoxFit.CONTAIN, visible=False)
        self.preview_note = ft.Text(size=11, color=color("#47747a"))
        self.frame_question = ft.TextField(
            hint_text="Напишите вопрос или говорите…", expand=True, text_size=13,
            color=color("#123b43"), bgcolor=color("#f3fffc"), on_submit=self.ask_frame,
        )
        self.visual_panel = ft.Column(visible=False, spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[self.preview, self.preview_note])
        self.files = []
        self.file_picker = None
        self.attachments = build_file_attachments(self.files, self.remove_file)
        self.user_text = ft.Text(size=12, color=color("#47747a"), selectable=True)
        self.reply_text = ft.Text(size=14, color=color("#123b43"), selectable=True)
        self.transcript = ft.Container(visible=False, padding=16, border_radius=16,
            bgcolor=color("#f3fffc"), border=ft.Border.all(1, color("#a8ddd7")),
            content=ft.Column(spacing=8, controls=[self.user_text, self.reply_text]))
        def labeled(button, label):
            return ft.Column(spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                             controls=[button, label if isinstance(label, ft.Text) else ft.Text(label, size=11, color=color("#47747a"))])
        self.panel = ft.Column(
            visible=False, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
                        controls=[self.orb, self.state_title, self.status_text, self.engine_text]),
                      ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=24, wrap=True,
                          controls=[labeled(self.mute_button, self.mute_label),
                                    labeled(self.camera_button, "Камера"), labeled(self.screen_button, "Экран"),
                                    labeled(self.sound_button, self.sound_label)]),
                      self.visual_panel, self.transcript],
        )
        self.composer = ft.Column(spacing=8, controls=[self.attachments,
                      ft.Row(spacing=8, controls=[brand_button(ft.Icons.ATTACH_FILE, "Добавить файлы в Live", self.add_files),
                          self.frame_question, brand_button(ft.Icons.SEND_ROUNDED, "Отправить вопрос в Live", self.ask_frame)]),
                      ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[self.interrupt_button])])
        self.summary = ft.Text(size=12, color=color("#123b43"), expand=True)
        self.status = ft.Row(visible=False, controls=[self.summary,
            ft.IconButton(icon=ft.Icons.OPEN_IN_FULL, tooltip="Открыть Live", on_click=self.open_call,
                          icon_color=color("#087f8c"))])
        self.start_button = ft.FilledButton(content="Начать разговор", icon=ft.Icons.CALL,
                                           on_click=self.toggle)
        self._state = "idle"
        self._stopped = threading.Event()
        self._turn_cancelled = threading.Event()
        self._task = None
        self._closed = False
        self._live_model = None
        self._preview_task = None
        self._last_frame = None
        self._last_source = None
        self._last_frame_time = 0
        self._preview_lock = asyncio.Lock()
        self._camera = None
        self._typed_question = None
        self._question_ready = asyncio.Event()
        self._vision_note = ""  # причина, по которой кадр камеры/экрана не получено
        self._dialog = None
        self.refresh_model_label()

    @property
    def busy(self):
        return self._state != "idle"

    def reconnect(self):
        self._closed = False
        self._render("")

    def _render(self, message):
        self._refresh_vision_buttons(update=False)
        self.status_text.value = message
        self.summary.value = message
        self.status.visible = bool(message) or self.camera_on or self.screen_on
        self.panel.visible = True
        self.state_title.value = {"idle": "Готов к разговору", "preparing": "Подключаю модель…",
            "listening": "Микрофон выключен" if self.microphone_muted else "Слушаю вас",
            "transcribing": "Распознаю речь…", "thinking": "Готовлю ответ…",
            "speaking": "Отвечаю", "interrupting": "Останавливаю ответ…",
            "stopping": "Завершаю разговор…"}.get(self._state, "Голосовой разговор")
        self.engine_text.value = model_display_name(self._live_model or get_selected_live_model()) + " · " + execution_label()
        self.start_button.content = "Завершить разговор" if self.busy else "Начать разговор"
        self.start_button.icon = ft.Icons.CALL_END if self.busy else ft.Icons.CALL
        self.interrupt_button.visible = self._state in {"transcribing", "thinking", "speaking", "interrupting"}
        self.interrupt_button.disabled = self._state == "interrupting"
        self.end_button.icon = ft.Icons.CALL_END if self.busy else ft.Icons.CLOSE
        self.end_button.tooltip = "Завершить Live" if self.busy else "Закрыть"
        self.button.content = ft.Icon(
            ft.Icons.CALL_END if self.busy else ft.Icons.GRAPHIC_EQ,
            color=ft.Colors.WHITE, size=20,
        )
        self.button.bgcolor = color("#d9364f") if self.busy else color("#ff6666ff")
        self.button.gradient = None if self.busy else brand_gradient()
        self.button.tooltip = (
            "Открыть текущий разговор Live"
            if self.busy
            else f"Live — {model_display_name(get_selected_live_model())}"
        )
        if not self._closed:
            self.page.update()

    async def open_call(self, _=None):
        self._render(self.status_text.value or "Говорите, пишите, прикрепляйте файлы. Камеру и экран можно включить по желанию.")
        if self._dialog is not None and self._dialog.open:
            return
        self._dialog = ft.AlertDialog(
            bgcolor=color("#eafffa"), modal=False, shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Row(controls=[ft.Icon(ft.Icons.GRAPHIC_EQ, color=color("#087f8c")),
                ft.Text("Live", size=20, weight=ft.FontWeight.W_600, color=color("#123b43"), expand=True),
                ft.IconButton(icon=ft.Icons.SETTINGS_OUTLINED, tooltip="Устройства Live", on_click=self.open_devices,
                    icon_color=color("#087f8c")),
                ft.IconButton(icon=ft.Icons.CLOSE, tooltip="Свернуть Live", on_click=lambda _: self.page.pop_dialog(),
                    icon_color=color("#087f8c"))]),
            content=ft.Column(width=max(220, min(620, self.page.width - 112)),
                height=max(200, min(540, self.page.height - 210)),
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[ft.Column(expand=True, scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[self.panel]), self.composer]),
            actions=[ft.TextButton(content="Свернуть", on_click=lambda _: self.page.pop_dialog()), self.start_button])
        self.page.show_dialog(self._dialog)

    async def end_call(self, _=None):
        await self.stop()
        if self._dialog is not None and self._dialog.open:
            self.page.pop_dialog()

    async def toggle_mute(self, _=None):
        self.microphone_muted = not self.microphone_muted
        self.mute_button.content = ft.Icon(ft.Icons.MIC_OFF if self.microphone_muted else ft.Icons.MIC,
                                          color=ft.Colors.WHITE, size=20)
        self.mute_button.tooltip = "Включить микрофон" if self.microphone_muted else "Выключить микрофон"
        self.mute_label.value = "Выключен" if self.microphone_muted else "Микрофон"
        if self._state == "listening":
            self._turn_cancelled.set()
        self._question_ready.set()
        self.page.update()

    async def toggle_sound(self, _=None):
        self.voice_output_enabled = not self.voice_output_enabled
        self.sound_button.content = ft.Icon(ft.Icons.VOLUME_UP if self.voice_output_enabled else ft.Icons.VOLUME_OFF,
                                            color=ft.Colors.WHITE, size=20)
        self.sound_button.tooltip = "Выключить озвучивание" if self.voice_output_enabled else "Включить озвучивание"
        self.sound_label.value = "Звук" if self.voice_output_enabled else "Без звука"
        if not self.voice_output_enabled and self._state == "speaking":
            self._turn_cancelled.set()
        self.page.update()

    def remove_file(self, file):
        if file in self.files:
            self.files.remove(file)
        self._render_files()

    def _render_files(self):
        row = build_file_attachments(self.files, self.remove_file)
        self.attachments.controls, self.attachments.visible = row.controls, row.visible
        self.page.update()

    async def add_files(self, _=None):
        try:
            if self.file_picker is None:
                self.file_picker = ft.FilePicker()
            store = self.get_material_store()
            files = await pick_materials(self.page, self.file_picker, store=store)
            if self._closed:
                return
            self.files.extend(file for file in files if file and all(file.path != existing.path for existing in self.files))
            self._render_files()
        except Exception as exc:
            self.frame_question.error_text = f"Не удалось добавить файл: {exc}"
            self.page.update()

    def open_devices(self, _=None):
        try:
            from ..services.devices import audio_devices, camera_devices
            from ..services.db import get_setting, get_db
        except ImportError:
            from services.devices import audio_devices, camera_devices
            from services.db import get_setting, get_db
        error = ft.Text("Изменения применятся со следующего запуска Live.", size=12, color=color("#47747a"))
        controls = []
        try:
            for key, label, choices in [("audio_input", "Микрофон", [("", "По умолчанию"), *audio_devices("input")]),
                                        ("audio_output", "Динамики", [("", "По умолчанию"), *audio_devices("output")]),
                                        ("camera_device", "Камера", camera_devices())]:
                control = ft.Dropdown(label=label, value=get_setting(key, "0" if key == "camera_device" else ""),
                                      color=color("#123b43"), bgcolor=color("#f3fffc"),
                                      options=[ft.DropdownOption(key=k, text=n) for k, n in dict(choices).items()])
                controls.append((key, control))
        except Exception as exc:
            error.value = str(exc)
        def save(_):
            try:
                for key, control in controls:
                    if control.value is not None:
                        get_db().set_setting(key, control.value)
                self.page.pop_dialog()
            except Exception as exc:
                error.value = str(exc)
                self.page.update()
        self.page.show_dialog(ft.AlertDialog(bgcolor=color("#eafffa"), title=ft.Text("Устройства Live", color=color("#123b43")),
            content=ft.Column(width=max(220, min(400, self.page.width - 112)), tight=True, controls=[*(c for _, c in controls), error]),
            actions=[ft.TextButton(content="Отмена", on_click=lambda _: self.page.pop_dialog()),
                     ft.FilledButton(content="Сохранить", on_click=save)]))

    def _set_state(self, state, message):
        self._state = state
        self._render(message)

    def refresh_model_label(self, _filename=None):
        if not self.busy:
            self.button.tooltip = f"Live — {model_display_name(get_selected_live_model())}"
            try:
                self.button.update()
            except Exception:
                pass

    def _refresh_vision_buttons(self, update=True):
        self.camera_button.border = ft.Border.all(3 if self.camera_on else 2, color("#087f8c") if self.camera_on else ft.Colors.WHITE)
        self.camera_button.content = ft.Icon(ft.Icons.VIDEOCAM if self.camera_on else ft.Icons.VIDEOCAM_OFF_OUTLINED,
                                             color=ft.Colors.WHITE, size=20)
        self.camera_button.tooltip = "Live — камера включена" if self.camera_on else "Live — показать с камеры"
        self.screen_button.border = ft.Border.all(3 if self.screen_on else 2, color("#087f8c") if self.screen_on else ft.Colors.WHITE)
        self.screen_button.content = ft.Icon(ft.Icons.STOP_SCREEN_SHARE_OUTLINED if self.screen_on else ft.Icons.SCREEN_SHARE_OUTLINED,
                                             color=ft.Colors.WHITE, size=20)
        self.screen_button.tooltip = "Live — экран включён" if self.screen_on else "Live — трансляция экрана"
        if not self._closed and update:
            self.page.update()

    async def toggle_camera(self, _=None):
        """Вкл/выкл передачи кадра с камеры модели перед каждым ответом. Камера и экран взаимоисключают друг друга —
        на одну реплику передаётся только одно изображение."""
        self.camera_on = not self.camera_on
        if self.camera_on:
            self.screen_on = False
        self._refresh_vision_buttons()
        await self._restart_preview()

    async def toggle_screen(self, _=None):
        """Вкл/выкл передачи снимка экрана модели перед каждым ответом."""
        self.screen_on = not self.screen_on
        if self.screen_on:
            self.camera_on = False
        self._refresh_vision_buttons()
        await self._restart_preview()

    async def _restart_preview(self):
        async with self._preview_lock:
            await self._replace_preview()

    async def _replace_preview(self):
        if self._preview_task is not None:
            self._preview_task.cancel()
            await asyncio.gather(self._preview_task, return_exceptions=True)
            self._preview_task = None
        if self._camera is not None:
            await asyncio.to_thread(self._camera.close)
            self._camera = None
        self._last_frame = self._last_source = None
        self.preview.visible = False
        self.visual_panel.visible = self.camera_on or self.screen_on
        if self.visual_panel.visible and not self._closed:
            self.preview_note.value = "Подключаю камеру…" if self.camera_on else "Подключаю экран…"
            if self.camera_on:
                try:
                    from ..services.db import get_setting
                except ImportError:
                    from services.db import get_setting
                self._camera = CameraStream(int(get_setting("camera_device", "0") or 0))
            self._preview_task = asyncio.create_task(self._preview_loop())
        if not self._closed:
            self.page.update()

    async def _preview_loop(self):
        source = "camera" if self.camera_on else "screen"
        try:
            while not self._closed and (self.camera_on or self.screen_on):
                try:
                    capture = self._camera.frame if source == "camera" else capture_screen_frame
                    pending = asyncio.create_task(asyncio.to_thread(capture))
                    try:
                        frame = await asyncio.shield(pending)
                    except asyncio.CancelledError:
                        await asyncio.gather(pending, return_exceptions=True)
                        raise
                    self._last_frame, self._last_source = frame, source
                    self._last_frame_time = time.monotonic()
                    self.preview.src = frame
                    self.preview.visible = True
                    self.preview_note.value = "Камера включена · кадр передаётся с каждым вопросом" if source == "camera" else "Экран включён · кадр передаётся с каждым вопросом"
                except Exception as exc:
                    self._last_frame = None
                    self.preview.visible = False
                    self.preview_note.value = str(exc)
                self.page.update()
                await asyncio.sleep(0.6 if source == "camera" else 1.2)
        except asyncio.CancelledError:
            pass

    async def ask_frame(self, _=None):
        text = (self.frame_question.value or "").strip()
        if not text:
            self.frame_question.error_text = "Введите вопрос"
            self.page.update()
            return
        if self._state in {"stopping", "interrupting"} or self._typed_question:
            self.frame_question.error_text = "Дождитесь отправки предыдущего вопроса"
            self.page.update()
            return
        if (self.camera_on or self.screen_on) and self._last_frame is None:
            self.frame_question.error_text = "Изображение ещё недоступно. Проверьте источник или выключите его."
            self.page.update()
            return
        if not self.busy and self.is_busy():
            self.frame_question.error_text = "Дождитесь завершения ответа в чате"
            self.page.update()
            return
        self._typed_question = text
        if not self.busy:
            await self.toggle()
            if not self.busy:
                self._typed_question = None
                return
        self.frame_question.value = ""
        self.frame_question.error_text = None
        self.page.update()
        self._question_ready.set()
        if self._state != "preparing":
            self._turn_cancelled.set()

    async def toggle(self, _=None):
        if self._closed:
            return
        if self.busy:
            await self.stop()
            return
        if self.is_busy():
            self._render("Дождитесь ответа ИИ или завершите диктовку перед запуском Live.")
            return
        if self.page.web and os.environ.get("XOPILOT_LOCAL_WEB") != "1":
            self._render("Live доступен в настольном приложении Xopilot.")
            return
        selected_model = get_selected_live_model()
        if not selected_model:
            self._render("Live: нужна модель с поддержкой аудио. Установите её в «Настройки → Модели».")
            return
        self._live_model = selected_model
        self._stopped = threading.Event()
        self._turn_cancelled = threading.Event()
        self._set_state(
            "preparing",
            f"Live · {model_display_name(selected_model)} · Подготавливаю голосовой разговор…",
        )
        if self.camera_on or self.screen_on:
            await self._restart_preview()
        self._task = asyncio.create_task(self._run())

    def _check_turn(self):
        if self._turn_cancelled.is_set() or self._stopped.is_set():
            raise CancelledError()

    async def _capture_vision_frame(self):
        """Кадр с камеры/экрана для текущей реплики, если включена соответствующая кнопка.
        Ошибка захвата (камера занята, Wayland без скриншотера и т.п.) не прерывает
        разговор — отвечаем без картинки, но причина показывается в статусе (_vision_note).
        """
        self._vision_note = ""
        if self.camera_on:
            source, message, capture = "Камера", "Live · Смотрю в камеру…", capture_camera_frame
        elif self.screen_on:
            source, message, capture = "Экран", "Live · Смотрю на экран…", capture_screen_frame
        else:
            return None
        self._set_state("thinking", message)
        expected = "camera" if self.camera_on else "screen"
        if self._last_frame is not None and self._last_source == expected and time.monotonic() - self._last_frame_time < 3:
            return self._last_frame
        try:
            if self.camera_on and self._camera is not None:
                capture = self._camera.frame
            return await asyncio.to_thread(capture)
        except Exception as exc:
            self._vision_note = f"{source}: {exc} Кадр не передан. Проверьте источник и повторите вопрос."
            raise VisionCaptureError(self._vision_note) from exc

    async def _run(self):
        error = ""
        try:
            if not self.microphone_muted:
                await asyncio.to_thread(check_live_audio)
            speaker = None
            model_filename = self._live_model or get_selected_live_model()
            if not model_filename:
                raise RuntimeError("Не выбрана модель Live.")
            await asyncio.to_thread(prepare_voice_model, self._stopped, model_filename)
            hint = "Говорите — отвечу после паузы."
            while not self._stopped.is_set():
                self._turn_cancelled = threading.Event()
                typed_turn = False
                try:
                    self._set_state("listening", f"Live · Слушаю. {hint}")
                    if self.microphone_muted and not self._typed_question:
                        notice = hint if hint not in {"Говорите — отвечу после паузы.", "Говорите — предыдущий ответ остановлен."} else ""
                        self._set_state("listening", notice + " Микрофон выключен. Напишите вопрос, добавьте файлы или включите микрофон.")
                        self._question_ready.clear()
                        await self._question_ready.wait()
                        self._check_turn()
                        if not self._typed_question:
                            continue
                    if self._typed_question:
                        typed_turn = True
                        transcript, self._typed_question = self._typed_question, None
                    else:
                        wav = await asyncio.to_thread(record_utterance, self._turn_cancelled)
                        self._check_turn()
                        self._set_state("transcribing", "Live · Распознаю вашу реплику…")
                        transcript = await asyncio.to_thread(
                            transcribe_audio, wav, self._turn_cancelled, model_filename
                        )
                        self._check_turn()
                    image_bytes = await self._capture_vision_frame()
                    self._check_turn()
                    sent_files = list(self.files)
                    attachments = [(file.name, file.path) for file in sent_files]
                    if attachments:
                        await self.on_user_message(transcript, attachments=attachments)
                    else:
                        await self.on_user_message(transcript)
                    for file in sent_files:
                        if file in self.files:
                            self.files.remove(file)
                    self.user_text.value, self.reply_text.value = transcript, ""
                    self.transcript.visible = True
                    self._render_files()
                    self._check_turn()
                    history = self.get_history()
                    self._set_state("thinking", "Live · Готовлю ответ…")
                    instructions, shared_files = self.get_resources()
                    reply = await asyncio.to_thread(
                        generate_live_reply, history, self._turn_cancelled, model_filename, image_bytes,
                        instructions=instructions, attachments=[*shared_files, *attachments],
                        **({"private": True} if self.is_private() else {}),
                    )
                    self._check_turn()
                    await self.on_ai_message(reply)
                    self.reply_text.value = reply
                    self.page.update()
                    self._check_turn()
                    speech_error = ""
                    if self.voice_output_enabled:
                        self._set_state("speaking", "Говорю. Можно перебить кнопкой или выключить звук.")
                        try:
                            if speaker is None:
                                speaker = await asyncio.to_thread(SpeechOutput)
                            await asyncio.to_thread(speaker.speak, reply, self._turn_cancelled)
                        except (CancelledError, asyncio.CancelledError):
                            raise
                        except Exception as exc:
                            speech_error = f"Ответ сохранён. Не удалось озвучить: {exc}"
                    # Дать динамикам закончить звучание перед повторным открытием микрофона.
                    await asyncio.sleep(0.25)
                    hint = speech_error or self._vision_note or "Говорите — отвечу после паузы."
                except SpeechNotRecognizedError:
                    hint = "Не разобрал речь. Повторите фразу."
                except VisionCaptureError as exc:
                    hint = str(exc)
                    if typed_turn and not self.frame_question.value:
                        self.frame_question.value = transcript
                        self.page.update()
                except (CancelledError, asyncio.CancelledError):
                    externally_cancelled = getattr(
                        asyncio.current_task(), "cancelling",
                        lambda: not (self._turn_cancelled.is_set() or self._stopped.is_set()),
                    )()
                    if externally_cancelled:
                        self._stopped.set()
                        self._turn_cancelled.set()
                        raise
                    hint = "Говорите — предыдущий ответ остановлен."
        except (CancelledError, asyncio.CancelledError):
            externally_cancelled = getattr(
                asyncio.current_task(), "cancelling", lambda: not self._stopped.is_set(),
            )()
            self._stopped.set()
            self._turn_cancelled.set()
            if externally_cancelled:
                raise
        except Exception as exc:
            if not self._stopped.is_set():
                error = f"Live: {exc}"
        finally:
            self.camera_on = self.screen_on = False
            self._typed_question = None
            await self._restart_preview()
            self._set_state("idle", error)

    async def interrupt(self, _=None):
        if self._state not in {"transcribing", "thinking", "speaking"}:
            return
        self._turn_cancelled.set()
        self._set_state("interrupting", "Live · Останавливаю ответ…")

    async def stop(self, _=None):
        if not self.busy:
            self.camera_on = self.screen_on = False
            await self._restart_preview()
            self._refresh_vision_buttons()
            self._render("")
            return
        self._stopped.set()
        self._turn_cancelled.set()
        self._question_ready.set()
        self._set_state("stopping", "Live · Завершаю разговор…")

    def clear_chat(self):
        """Discard the previous chat's visible transcript and pending attachments."""
        self.files.clear()
        self.attachments.controls.clear()
        self.attachments.visible = False
        self.user_text.value = self.reply_text.value = self.frame_question.value = ''
        self.frame_question.error_text = None
        self.transcript.visible = False
        self._typed_question = None
        self._last_frame = self._last_source = None
        self._last_frame_time = 0

    async def close(self, _=None):
        self._closed = True
        await self.stop()
        self.camera_on = self.screen_on = False
        await self._restart_preview()
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)
