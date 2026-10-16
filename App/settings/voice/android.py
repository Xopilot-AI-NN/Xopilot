"""
Файл: /App/settings/voice/android.py
Разработчик: DenBroLiik
Версия: 2.0.9
Описание: Проверка системных офлайн-голосов по каждому языку без ложного общего отказа.
"""
import asyncio
import threading
import flet as ft
try:
    from ...app.theme.palette import color
    from ...services.mobile_runtime import call_async
    from ...services.mobile_audio import AndroidSpeechOutput
    from ...services.external_browser import open_external
except ImportError:
    from app.theme.palette import color
    from services.mobile_runtime import call_async
    from services.mobile_audio import AndroidSpeechOutput
    from services.external_browser import open_external

VOICE_DOWNLOAD_URL = 'https://f-droid.org/packages/com.github.olga_yakovleva.rhvoice.android/'


def build_android_voice_controls(page, on_status):
    feedback = ft.Text('Проверяю синтез речи…', size=12, color=color('#47747a'))

    async def refresh():
        try:
            state = await call_async('speechEngines')
            engines = state.get('engines', [])
            preferred = next((engine for engine in engines if engine['id'] == state.get('preferred')), None)
            if not engines:
                feedback.value = 'Движок синтеза речи не установлен. Установите RHVoice, скачайте голоса и выберите его в настройках Android.'
            elif preferred:
                feedback.value = 'Движок: ' + preferred['name'] + '. Проверьте, что русский и английский голоса скачаны для работы без сети.'
            else:
                feedback.value = 'Выберите движок в настройках Android: ' + ', '.join(engine['name'] for engine in engines)
        except Exception:
            feedback.value = 'Не удалось проверить синтез речи. Откройте настройки голоса Android.'
        page.update()

    async def settings(_):
        try:
            await call_async('speechSettings')
        except Exception:
            feedback.value = 'Не удалось открыть настройки. Найдите «Синтез речи» в настройках телефона.'
            page.update()

    async def download(_):
        try:
            await open_external(VOICE_DOWNLOAD_URL)
        except Exception:
            feedback.value = 'Не удалось открыть браузер. RHVoice доступен на f-droid.org.'
            page.update()

    async def preview(_):
        preview_button.disabled = True
        feedback.value = 'Проверяю русскую и английскую озвучку…'
        page.update()
        try:
            state = await call_async('speechEngines')
            if not state.get('engines'):
                raise RuntimeError('Сначала установите движок синтеза речи и скачайте голоса.')
            results=[];ready=0
            for label,text in [('Русский','Привет! Это голос Xopilot.'),('English','Hello! This is the Xopilot voice.')]:
                try:
                    await asyncio.to_thread(AndroidSpeechOutput().speak,text,threading.Event())
                    results.append(label+': озвучено');ready+=1
                except Exception as error:
                    results.append(label+': '+str(error).removeprefix('Bad state: '))
            feedback.value='\n'.join(results)
            on_status('Озвучивание проверено' if ready==2 else 'Озвучивание проверено частично' if ready else 'Озвучивание не готово')
        except Exception as error:
            feedback.value = str(error)
            on_status('Озвучивание не готово')
        finally:
            preview_button.disabled = False
            page.update()

    preview_button = ft.OutlinedButton(content='Прослушать', icon=ft.Icons.VOLUME_UP, on_click=preview)
    page.run_task(refresh)
    return ft.Column(spacing=8, controls=[
        ft.Text('Системный офлайн-голос Android', size=14, weight=ft.FontWeight.W_600, color=color('#123b43')),
        ft.Text('Установите движок, скачайте русский и английский голоса, затем выберите его в настройках синтеза речи. '
                'COVE, Miku и Maple пока доступны на ПК.', size=12, color=color('#47747a')),
        ft.Row(wrap=True, spacing=8, controls=[
            ft.OutlinedButton(content='Настройки голоса', icon=ft.Icons.SETTINGS_VOICE, on_click=settings),
            ft.OutlinedButton(content='Скачать RHVoice', icon=ft.Icons.DOWNLOAD, on_click=download),
            preview_button,
        ]), feedback,
    ])
