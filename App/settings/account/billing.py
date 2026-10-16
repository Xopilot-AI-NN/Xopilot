"""Plan comparison and resumable, server-confirmed monthly checkout."""
import asyncio
from datetime import datetime
import flet as ft
try:
    from ...services import billing, cloud_account
    from ...services.db import get_db
    from ...app.theme.palette import color, modern_input
    from ...app.menu.buttons.actions import action_button
except ImportError:
    from services import billing, cloud_account
    from services.db import get_db
    from app.theme.palette import color, modern_input
    from app.menu.buttons.actions import action_button


def open_billing(page):
    preference = modern_input(ft.Dropdown(label='Валюта цен',
        value=get_db().get_setting('display_currency') or 'auto',
        options=[ft.DropdownOption(key=k, text=v) for k, v in billing.CURRENCIES.items()]))
    account_label = ft.Text('Получаем данные подписки…', size=15, weight=ft.FontWeight.W_600, color=color('#123b43'))
    detail = ft.Text('', size=12, color=color('#47747a'))
    cards = ft.ResponsiveRow(spacing=12, run_spacing=12)
    status = ft.Text('', size=12, color=color('#47747a'))
    progress = ft.ProgressBar(color=color('#087f8c'))
    retry = action_button('Повторить загрузку', icon=ft.Icons.REFRESH, secondary=True)
    retry.visible = False
    operation = False
    generation = 0
    closed = False
    owner = (cloud_account.state() or {}).get('account_id')

    def current():
        return not closed and (cloud_account.state() or {}).get('account_id') == owner

    def close(_=None):
        nonlocal closed, generation
        closed = True
        generation += 1

    def dismiss(_):
        close()
        page.pop_dialog()

    async def purchase(plan):
        nonlocal operation
        if operation or not current(): return
        operation = True
        cards.disabled = True
        status.value = 'Подготавливаем заказ…'
        page.update()
        try:
            order = await asyncio.to_thread(billing.create_order, plan)
            if current():
                open_order(order)
                status.value = ''
        except Exception as exc:
            if current(): status.value = str(exc)
        finally:
            operation = False
            cards.disabled = False
            if current(): page.update()

    def open_order(order):
        ended = False
        checking = False
        polling = None
        feedback = ft.Text('Укажите сумму в RUB и вставьте код заказа в сообщение платежа. '
            'Доступ активируется после подтверждения сервером.', size=12, color=color('#47747a'))
        code = modern_input(ft.TextField(label='Код заказа', value=order['payment_message'], read_only=True))
        clipboard = ft.Clipboard()
        browser = action_button('Перейти к оплате', icon=ft.Icons.OPEN_IN_NEW)
        check = action_button('Проверить оплату', icon=ft.Icons.CHECK_CIRCLE_OUTLINE, secondary=True)
        copy = action_button('Скопировать код', icon=ft.Icons.CONTENT_COPY, secondary=True)

        def stop(_=None):
            nonlocal ended
            ended = True
            # The monitor may itself complete payment: do not cancel its own
            # future before it refreshes the subscription. It exits on ended.

        def leave(_):
            stop()
            page.pop_dialog()
            page.run_task(refresh)

        async def copy_code(_):
            try:
                await clipboard.set(order['payment_message'])
                feedback.value = 'Код скопирован. Вставьте его целиком в сообщение DonationAlerts.'
            except Exception:
                feedback.value = 'Не удалось скопировать. Выделите код в поле и скопируйте вручную.'
            if not ended and current(): page.update()

        async def launch(_):
            browser.disabled = True
            page.update()
            try:
                try: from ...services.external_browser import open_external
                except ImportError: from services.external_browser import open_external
                await open_external(order['payment_url'])
                feedback.value = 'После оплаты вернитесь в Xopilot. Проверяем автоматически; можно нажать «Проверить оплату».'
            except Exception as exc: feedback.value = str(exc)
            finally:
                browser.disabled = False
                if not ended and current(): page.update()

        async def confirm(_=None, automatic=False):
            nonlocal checking
            if checking or ended or not current(): return
            checking = True
            check.disabled = True
            if not automatic:
                feedback.value = 'Проверяем платёж…'
                page.update()
            try:
                result = await asyncio.to_thread(billing.check_order, order['id'])
                if ended or not current(): return
                if result['status'] == 'paid':
                    stop()
                    page.pop_dialog()
                    await refresh()
                    if current(): status.value = 'Оплата подтверждена. Подписка активирована.'
                    page.update()
                    return
                if result['status'] in ('expired', 'cancelled'):
                    feedback.value = ('Срок заказа истёк.' if result['status'] == 'expired' else 'Заказ отменён.')
                    feedback.value += ' Если уже оплатили, обратитесь в поддержку: support@xopilot.by.'
                    browser.disabled = True
                    stop()
                    page.update()
                    return
                if not automatic:
                    feedback.value = 'Платёж пока не найден. Проверьте сумму, RUB и код. '
                    feedback.value += 'Автоматическая проверка — каждые 30 секунд, пока открыто это окно.'
            except Exception as exc:
                if not ended and current(): feedback.value = str(exc)
            finally:
                checking = False
                check.disabled = ended
                if not ended and current(): page.update()

        async def monitor():
            while not ended and current():
                await asyncio.sleep(30)
                await confirm(automatic=True)

        browser.on_click, check.on_click, copy.on_click = launch, confirm, copy_code
        plan_name = next(p['name'] for p in billing.PLANS if p['id'] == order['plan'])
        payment = ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text('Оплата подписки', color=color('#123b43')),
            content=ft.Column(width=440, height=min(500, max(260, (page.height or 840)-200)),
                scroll=ft.ScrollMode.AUTO, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[ft.Text(plan_name, size=18, weight=ft.FontWeight.BOLD, color=color('#123b43')),
                    ft.Text(f"{order['amount_kopecks']/100:g} RUB / месяц", size=24,
                            weight=ft.FontWeight.BOLD, color=color('#087f8c')),
                    ft.Text('Календарный месяц · без автосписаний', size=12, color=color('#47747a')),
                    code, copy, feedback, browser, check,
                    ft.Text('Закрытие окна сохраняет заказ. Продолжить можно в разделе подписок. '
                            'Заказ действует 48 часов.', size=11, color=color('#47747a'))]),
            actions=[ft.TextButton(content='Закрыть', on_click=leave)], on_dismiss=stop)
        payment._xopilot_full_width = True
        page.show_dialog(payment)
        polling = page.run_task(monitor)

    async def refresh(_=None):
        nonlocal generation
        if not current(): return
        generation += 1
        revision = generation
        progress.visible = True
        retry.visible = False
        page.update()
        try:
            account_error = ''
            try: account = await asyncio.to_thread(billing.account_status)
            except Exception as exc:
                account = {'enabled': False, 'signed_in': bool(owner), 'plan': None}
                account_error = str(exc)
            values = await asyncio.to_thread(billing.prices, account.get('approved_discount'))
            if revision != generation or not current(): return
            plan_id = account.get('plan')
            title = next((p['name'] for p in billing.PLANS if p['id'] == plan_id), None)
            account_label.value = ('Текущий тариф: ' + title) if title else 'Не удалось загрузить подписку'
            expiry = account.get('expires_at')
            detail.value = ('Действует до '+datetime.fromtimestamp(expiry).strftime('%d.%m.%Y')+'. Продление вручную.'
                            if expiry else '128 МБ зашифрованного облачного хранилища.')
            ready = account.get('enabled', False)
            if not account.get('signed_in'): detail.value = 'Войдите в аккаунт, чтобы оформлять подписку.'
            elif not ready and not account_error:
                detail.value += '\nПродажи ещё не открыты. Условия тарифов — ниже; существующие функции доступны в ознакомительном режиме.'
            elif account.get('limits_enforced'):
                detail.value += '\nДоступ к удалённым заданиям определяется действующей подпиской на сервере.'
            rows = []
            pending = account.get('pending_order')
            if pending:
                async def cancel_pending(_):
                    nonlocal operation
                    if operation or not current(): return
                    operation = True
                    cards.disabled = True
                    page.update()
                    try:
                        await asyncio.to_thread(billing.cancel_order, pending['id'])
                        await refresh()
                    except Exception as exc:
                        if current(): status.value = str(exc)
                    finally:
                        operation = False
                        cards.disabled = False
                        if current(): page.update()
                rows.append(ft.Container(col=12, padding=14, border_radius=16, bgcolor=color('#dff8f3'),
                    border=ft.Border.all(1, color('#a8ddd7')), content=ft.Column(spacing=10, controls=[
                        ft.Text('Незавершённый заказ', weight=ft.FontWeight.BOLD, color=color('#123b43')),
                        ft.Text(next(p['name'] for p in billing.PLANS if p['id']==pending['plan'])+
                            f" · {pending['amount_kopecks']/100:g} RUB", size=12, color=color('#47747a')),
                        ft.Row(wrap=True, controls=[action_button('Продолжить оплату', disabled=not ready,
                            on_click=lambda _: page.run_task(purchase, pending['plan'])),
                            action_button('Отменить заказ', secondary=True, on_click=cancel_pending)])])))
            active_paid = plan_id in ('elite', 'ultra', 'led')
            for plan in values['plans']:
                selected = plan_id == plan['id']
                conflict = (active_paid and not selected) or (pending and pending['plan'] != plan['id'])
                description = [ft.Text(plan['name'], size=18, weight=ft.FontWeight.BOLD, color=color('#123b43')),
                    ft.Text(plan['label']+(' / месяц' if plan['rub'] else ''), size=22,
                            weight=ft.FontWeight.BOLD, color=color('#087f8c'))]
                if plan.get('base_label'):
                    description.append(ft.Text('Оплата: '+plan['base_label'], size=11, color=color('#47747a')))
                description += [ft.Text('• '+f, size=13, color=color('#123b43')) for f in plan['features']]
                description.append(ft.Text('128 МБ хранилища', size=12, color=color('#47747a')))
                if selected:
                    description.append(ft.Text('Ваш тариф', size=12, weight=ft.FontWeight.BOLD, color=color('#087f8c')))
                if plan['id']=='elite' and account.get('approved_discount') in billing.DISCOUNTS:
                    description.append(ft.Text('Подтверждённая скидка: '+str(billing.DISCOUNTS[account['approved_discount']])+'%',
                                               size=12, color=color('#087f8c')))
                if plan['rub']:
                    description.append(action_button('Продлить на месяц' if selected else 'Оформить на месяц',
                        disabled=not ready or bool(conflict),
                        on_click=lambda _, key=plan['id']: page.run_task(purchase, key)))
                    if conflict and ready:
                        description.append(ft.Text('Сначала завершите текущий заказ.' if pending else
                            'Смена тарифа доступна после окончания текущей подписки.', size=11, color=color('#47747a')))
                rows.append(ft.Container(col={'xs':12, 'sm':6}, padding=16, border_radius=20,
                    bgcolor=color('#ffffff'), border=ft.Border.all(2 if selected else 1,
                    color('#087f8c' if selected else '#a8ddd7')),
                    content=ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=description)))
            cards.controls = rows
            status.value = 'Оплата в RUB. Валюта цен сохраняется автоматически. Автосписаний нет.'
            if values.get('rate_date'): status.value += '\nОриентировочный курс Банка России от '+values['rate_date']+'.'
            elif values['currency'] != 'RUB': status.value += '\nКурс недоступен: показаны цены в RUB.'
            status.value += '\nДокументы для скидки Elite: support@xopilot.by. Пакеты токенов подключим отдельно.'
            status.value += '\nНа всех тарифах — 128 МБ облачного хранилища. Локальные Gemma, свой API, Canvas, документы, библиотека и защищённые чаты доступны бесплатно. '
            status.value += 'Запросы по собственному API-ключу оплачиваются вашему провайдеру и не входят в тариф Zephyr. '
            status.value += 'Объём включённых токенов Elite/Ultra будет указан перед запуском продажи. '
            status.value += 'Ограничения удалённых заданий включаются вместе с продажами. Подписка не отменяет разрешения устройств и подтверждения команд.'
            if account_error:
                status.value = account_error
                retry.visible = True
        except Exception as exc:
            if current() and revision == generation:
                status.value = str(exc)
                retry.visible = True
        finally:
            if current() and revision == generation:
                progress.visible = False
                page.update()

    async def changed(_):
        billing.set_currency(preference.value)
        await refresh()

    preference.on_select = changed
    retry.on_click = refresh
    dialog = ft.AlertDialog(bgcolor=color('#eafffa'), shape=ft.RoundedRectangleBorder(radius=22),
        title=ft.Text('Подписка Zephyr', color=color('#123b43')),
        content=ft.Column(width=700, height=min(640, max(280, (page.height or 840)-200)),
            scroll=ft.ScrollMode.AUTO, spacing=16, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[account_label, detail, preference, progress, cards, status, retry]),
        actions=[ft.TextButton(content='Закрыть', on_click=dismiss)], on_dismiss=close)
    dialog._xopilot_full_width = True
    page.show_dialog(dialog)
    page.run_task(refresh)
