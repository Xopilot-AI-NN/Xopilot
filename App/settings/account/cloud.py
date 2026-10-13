"""Real cloud account controls; chat uploads remain separately opt-in."""
import asyncio
import time
from datetime import datetime
import flet as ft

try:
    from ...services import cloud_account
    from ...app.palette import color, modern_input
    from ...app.buttons.actions import action_button
except ImportError:
    from services import cloud_account
    from app.palette import color, modern_input
    from app.buttons.actions import action_button


def build_cloud_card(page):
    content = ft.Column(spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    feedback = ft.Text('', size=12, color=color('#47747a'))
    card = ft.Container(padding=14, bgcolor=color('#ffffff'), border_radius=20,
                        border=ft.Border.all(1, color('#b9eee4')), content=content)

    def render():
        account = cloud_account.state()
        controls = [ft.Row(controls=[ft.Icon(ft.Icons.CLOUD_OUTLINED, color=color('#087f8c')),
                    ft.Text('Облачный аккаунт', size=18, weight=ft.FontWeight.BOLD, color=color('#123b43'))])]
        if account:
            controls += [ft.Text(account['email'], size=12, color=color('#47747a')),
                         ft.Row(wrap=True, spacing=10, controls=[
                             action_button('Устройства', icon=ft.Icons.DEVICES_OUTLINED, secondary=True, on_click=open_devices),
                             action_button('Выйти', icon=ft.Icons.LOGOUT, secondary=True, on_click=sign_out)])]
            if account.get('google_linked'):
                controls.append(ft.Text('Google подключён',size=12,color=color('#087f8c')))
            else:
                controls.append(action_button('Привязать Google',secondary=True,on_click=lambda _:page.run_task(google_sign_in,True)))
        else:
            controls += [ft.Text('Войдите, чтобы управлять аккаунтом и устройствами.', color=color('#47747a'), size=12),
                         ft.Row(wrap=True, controls=[action_button('Войти', on_click=open_login),
                             action_button('Создать аккаунт', secondary=True,on_click=lambda e: open_login(e, register=True))])]
            controls.append(action_button('Продолжить с Google', secondary=True,on_click=lambda _: page.run_task(google_sign_in, False)))
        from .storage import open_storage
        from .billing import open_billing
        from .sync import open_sync
        def tile(icon,title,subtitle,callback,disabled=False):
            return ft.Container(padding=12,border_radius=16,bgcolor=color('#dff8f3'),
                border=ft.Border.all(1,color('#b9eee4')),ink=not disabled,on_click=callback if not disabled else None,
                content=ft.Row(spacing=12,controls=[ft.Container(width=40,height=40,border_radius=20,
                    border=ft.Border.all(2,color('#ffffff')),gradient=ft.LinearGradient(colors=['#00d6a3','#08a9d9','#7657ff']),
                    alignment=ft.Alignment.CENTER,content=ft.Icon(icon,color=ft.Colors.WHITE,size=21)),
                    ft.Column(expand=True,spacing=3,controls=[ft.Text(title,weight=ft.FontWeight.BOLD,color=color('#123b43')),
                        ft.Text(subtitle,size=11,color=color('#47747a'))]),ft.Icon(ft.Icons.CHEVRON_RIGHT,color=color('#087f8c'))]))
        controls += [tile(ft.Icons.SYNC,'Синхронизация','Данные, профиль и лимит трафика' if account else 'Войдите, чтобы включить синхронизацию',lambda _:open_sync(page),not bool(account)),
            tile(ft.Icons.STORAGE_ROUNDED,'Хранилище','Материалы, занятое место и удаление копий',lambda _:open_storage(page)),
            tile(ft.Icons.PAYMENTS_OUTLINED,'Подписка Zephyr','Текущий тариф, условия и продление',lambda _:open_billing(page)),
            ft.Text('Содержимое шифруется на устройстве. Временные чаты остаются локальными.',color=color('#47747a'),size=11),feedback]
        content.controls = controls
        refresh=getattr(page,'_xopilot_profile_refresh',None)
        if callable(refresh):refresh()

    async def refresh_google_data():
        try:
            warning=await asyncio.to_thread(cloud_account.refresh_google_profile)
            if warning:feedback.value=warning
        except Exception as exc:feedback.value=str(exc)
        render();page.update()

    google_busy = False

    async def google_sign_in(link=False):
        nonlocal google_busy
        if google_busy:
            return
        google_busy = True
        pending = None
        cancelled = False
        closed = False
        status = ft.Text('Открываем вход через Google…', size=13, color=color('#47747a'))
        launch = action_button('Открыть браузер', icon=ft.Icons.OPEN_IN_NEW, secondary=True)
        abort = ft.TextButton(content='Отмена')

        def close_dialog():
            nonlocal closed
            if not closed:
                closed = True
                page.pop_dialog()

        async def open_browser(_):
            try:
                try:
                    from ...services.external_browser import open_external
                except ImportError:
                    from services.external_browser import open_external
                await open_external(pending['browser_url'])
                status.value = 'Выберите аккаунт Google в браузере, затем вернитесь в Xopilot.'
            except Exception:
                status.value = 'Не удалось открыть браузер. Нажмите «Открыть браузер» для повторной попытки.'
            page.update()

        async def stop(_):
            nonlocal cancelled
            cancelled = True
            abort.disabled = launch.disabled = True
            status.value = 'Завершаем запрос…'
            page.update()
            try:
                if pending:
                    await asyncio.to_thread(cloud_account.cancel_google, pending)
            except Exception:
                # The server also expires all abandoned flows after 10 minutes.
                pass
            close_dialog()
            render()
            page.update()

        try:
            feedback.value = 'Подготавливаем вход Google…'
            page.update()
            pending = await asyncio.to_thread(cloud_account.begin_google, link=link)
            launch.on_click = open_browser
            abort.on_click = stop
            page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'),
                title=ft.Text('Привязать Google' if link else 'Вход через Google'),
                content=ft.Column(width=380, tight=True, spacing=16, controls=[
                    ft.ProgressRing(width=28, height=28), status,
                    ft.Text('Пароль Google вводится только на сайте Google. Пароль шифрования синхронизации остаётся отдельным.',
                            size=12, color=color('#47747a'))]), actions=[abort, launch]))
            await open_browser(None)
            started = time.monotonic()
            while not cancelled and time.monotonic() - started < 600:
                try:
                    completed = await asyncio.to_thread(cloud_account.poll_google, pending)
                except cloud_account.CloudError as exc:
                    if exc.code not in ('connection_failed', 'google_unavailable', 'storage_unavailable'):
                        raise
                    status.value = 'Восстанавливаем соединение. После входа вернитесь в Xopilot.'
                    page.update()
                    await asyncio.sleep(4)
                    continue
                if completed:
                    if not cancelled:
                        close_dialog()
                        warning=(cloud_account.state() or {}).get('google_profile_warning')
                        feedback.value = warning or ('Данные Google обновлены' if link else 'Вход через Google выполнен')
                        render()
                    break
                await asyncio.sleep(4)
            else:
                if not cancelled:
                    raise cloud_account.CloudError('google_expired')
        except Exception as exc:
            feedback.value = str(exc)
            if pending and not closed:
                close_dialog()
        finally:
            if pending:
                try:
                    await asyncio.to_thread(cloud_account.cancel_google, pending)
                except Exception:
                    pass
            google_busy = False
            page.update()

    def open_login(_, register=False):
        username = modern_input(ft.TextField(label='Имя пользователя', autofocus=register))
        email = modern_input(ft.TextField(label='Почта', autofocus=not register, keyboard_type=ft.KeyboardType.EMAIL))
        password = modern_input(ft.TextField(label='Пароль', password=True, can_reveal_password=True))
        repeat = modern_input(ft.TextField(label='Повторный пароль', password=True, can_reveal_password=True))
        fields = [username, email, password, repeat] if register else [email, password]
        error = ft.Text('', size=12, color=color('#087f8c'))
        busy = ft.ProgressRing(width=20, height=20, visible=False)
        submit = action_button('Создать' if register else 'Войти')
        cancel = ft.TextButton(content='Отмена')

        def clear_passwords():
            password.value = repeat.value = ''

        async def send(_):
            if submit.disabled:
                return
            error.value = ''
            submit.disabled = cancel.disabled = True
            busy.visible = True
            for field in fields:
                field.disabled = True
            page.update()
            try:
                if register:
                    pending = await asyncio.to_thread(cloud_account.begin_registration,
                        username.value or '', email.value or '', password.value or '', repeat.value or '')
                    clear_passwords()
                    page.pop_dialog()
                    open_confirmation(pending)
                else:
                    await asyncio.to_thread(cloud_account.sign_in, email.value or '', password.value or '')
                    clear_passwords()
                    page.pop_dialog()
                    feedback.value = 'Вход выполнен'
                    render()
            except Exception as exc:
                error.value = str(exc)
            finally:
                submit.disabled = cancel.disabled = False
                busy.visible = False
                for field in fields:
                    field.disabled = False
                page.update()

        def close(_):
            if not submit.disabled:
                clear_passwords()
                page.pop_dialog()

        def switch(_):
            if not submit.disabled:
                close(None)
                open_login(None, not register)

        def google_from_dialog(_):
            if not submit.disabled:
                close(None)
                page.run_task(google_sign_in, False)

        submit.on_click = send
        (repeat if register else password).on_submit = send
        cancel.on_click = close
        page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'),
            title=ft.Text('Создать аккаунт' if register else 'Вход в Xopilot'),
            content=ft.Column(width=380, height=390 if register else 260, spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH, scroll=ft.ScrollMode.AUTO,
                controls=[*fields, error, busy, action_button('Продолжить с Google', secondary=True,on_click=google_from_dialog), ft.TextButton(
                    content='Уже есть аккаунт? Войти' if register else 'Создать аккаунт', on_click=switch)]),
            actions=[cancel, submit]))

    def open_confirmation(pending):
        code = modern_input(ft.TextField(label='Код из письма', max_length=6, autofocus=True,
                                       keyboard_type=ft.KeyboardType.NUMBER))
        error = ft.Text('', size=12, color=color('#087f8c'))
        submit = action_button('Подтвердить')
        resend = ft.TextButton(content='Отправить код ещё раз')
        cancel = ft.TextButton(content='Отмена')
        sent_at = time.monotonic()

        async def confirm(_):
            submit.disabled = resend.disabled = cancel.disabled = True
            error.value = ''
            page.update()
            try:
                await asyncio.to_thread(cloud_account.confirm_registration, pending['registration_id'], code.value or '')
                code.value = ''
                page.pop_dialog()
                feedback.value = 'Почта подтверждена. Аккаунт создан'
                render()
            except Exception as exc:
                error.value = str(exc)
            finally:
                submit.disabled = resend.disabled = cancel.disabled = False
                page.update()

        async def send_again(_):
            nonlocal sent_at
            remaining = 60 - int(time.monotonic() - sent_at)
            if remaining > 0:
                error.value = f'Повторная отправка через {remaining} сек.'
                page.update()
                return
            resend.disabled = submit.disabled = cancel.disabled = True
            page.update()
            try:
                await asyncio.to_thread(cloud_account.resend_confirmation, pending['registration_id'])
                sent_at = time.monotonic()
                error.value = 'Новый код отправлен'
            except Exception as exc:
                error.value = str(exc)
            finally:
                resend.disabled = submit.disabled = cancel.disabled = False
                page.update()
        submit.on_click = code.on_submit = confirm
        resend.on_click = send_again
        cancel.on_click = lambda _: page.pop_dialog()
        page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), title=ft.Text('Подтвердите почту'),
            content=ft.Column(width=380, height=240, spacing=12, scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[ft.Text('Мы отправили код на ' + pending['email']), code,
                          ft.Text('Код действует 20 минут', size=12), error, resend]), actions=[cancel, submit]))

    async def sign_out(_):
        feedback.value = 'Завершаем сессию на сервере…'
        page.update()
        try:
            await asyncio.to_thread(cloud_account.sign_out)
            feedback.value = 'Вы вышли из аккаунта'
            render()
        except Exception as exc:
            feedback.value = str(exc)
            def remove_offline(_):
                cloud_account.sign_out(local_only=True)
                feedback.value = 'Аккаунт удалён с устройства. Серверная сессия не отозвана: завершите её с другого устройства.'
                page.pop_dialog()
                render()
                page.update()
            page.show_dialog(ft.AlertDialog(modal=True, bgcolor=color('#eafffa'), title=ft.Text('Сервер недоступен'),
                content=ft.Text('Можно удалить вход с этого устройства. Сессия на сервере останется активной до отзыва или истечения срока.'),
                actions=[ft.TextButton(content='Оставить вход', on_click=lambda _: page.pop_dialog()),
                         ft.OutlinedButton(content='Удалить вход с устройства', on_click=remove_offline)]))
        page.update()

    async def open_devices(_):
        devices = ft.Column(width=460, height=330, tight=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        status = ft.Text('Загружаем устройства…', size=12, color=color('#47747a'))
        dialog = ft.AlertDialog(bgcolor=color('#eafffa'), title=ft.Text('Устройства и сессии'),
            content=ft.Column(tight=True, controls=[status, devices]),
            actions=[ft.TextButton(content='Закрыть', on_click=lambda _: page.pop_dialog())])
        page.show_dialog(dialog)

        async def refresh():
            devices.controls = []
            try:
                rows = await asyncio.to_thread(cloud_account.sessions)
                status.value = f'Активных сессий: {len(rows)}'
                for session in rows:
                    name = session['device_name'] + (' · это устройство' if session['current'] else '')
                    last = datetime.fromtimestamp(session['last_used_at']).strftime('%d.%m.%Y %H:%M')
                    def rename(_,identifier=session['id'],previous=session['device_name']):
                        field=modern_input(ft.TextField(label='Название устройства',value=previous,max_length=120))
                        error=ft.Text('',size=12)
                        async def save(_):
                            try:
                                await asyncio.to_thread(cloud_account.rename_session,identifier,field.value or '')
                                page.pop_dialog();await refresh()
                            except Exception as exc:error.value=str(exc);page.update()
                        page.show_dialog(ft.AlertDialog(title=ft.Text('Название устройства'),bgcolor=color('#eafffa'),
                            content=ft.Column(width=380,tight=True,controls=[field,error]),
                            actions=[ft.TextButton(content='Отмена',on_click=lambda _:page.pop_dialog()),action_button('Сохранить',on_click=save)]))
                    async def revoke(_, identifier=session['id'], current=session['current']):
                        try:
                            await asyncio.to_thread(cloud_account.revoke_session, identifier)
                            if current:
                                page.pop_dialog()
                                feedback.value = 'Сессия завершена'
                                render()
                            else:
                                await refresh()
                        except Exception as exc:
                            status.value = str(exc)
                        page.update()
                    devices.controls.append(ft.Container(padding=12, border_radius=14, bgcolor=color('#dff8f3'),
                        content=ft.Row(controls=[ft.Icon(ft.Icons.DEVICES_OUTLINED, color=color('#087f8c')),
                            ft.Column(expand=True, spacing=4, controls=[ft.Text(name, color=color('#123b43')),
                                ft.Text('Последнее обновление: ' + last, size=11, color=color('#47747a'))]),
                            ft.IconButton(icon=ft.Icons.EDIT_OUTLINED,tooltip='Переименовать устройство',on_click=rename),
                            ft.IconButton(icon=ft.Icons.LOGOUT, tooltip='Завершить сессию ' + session['device_name'], on_click=revoke)])))
            except Exception as exc:
                status.value = str(exc)
                if cloud_account.state() is None:
                    render()
            page.update()
        await refresh()

    render()
    if (cloud_account.state() or {}).get('google_linked'):
        page.run_task(refresh_google_data)
    return card
