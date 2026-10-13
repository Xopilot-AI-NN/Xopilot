"""Checkout boundaries and native Android browser routing; no real payments."""
import unittest
from unittest.mock import patch,Mock,AsyncMock
import asyncio
import flet as ft
import uuid
from App.services import billing,cloud_account,external_browser,mobile_runtime


class CheckoutTests(unittest.TestCase):
    def order(self):
        key=uuid.uuid4()
        return {'id':str(key),'amount_kopecks':100000,'currency':'RUB',
            'payment_url':'https://www.donationalerts.com/r/denbroliik',
            'payment_message':'XOPILOT-'+key.hex,'plan':'elite'}

    def test_checkout_sends_only_plan_and_uses_server_quote(self):
        order=self.order();order['amount_kopecks']=60000
        with patch.object(cloud_account,'request',return_value=order) as request:
            self.assertEqual(billing.create_order('elite')['amount_kopecks'],60000)
            request.assert_called_once_with('/billing/orders',method='POST',body={'plan':'elite'})

    def test_untrusted_payment_links_and_amounts_are_rejected(self):
        for field,value in [('payment_url','https://attacker.invalid/r/denbroliik'),
                            ('payment_url','http://www.donationalerts.com/r/denbroliik'),
                            ('payment_url','https://www.donationalerts.com/r/denbroliik?redirect=evil'),
                            ('amount_kopecks',True),('amount_kopecks',0),('amount_kopecks',700001),
                            ('currency','BYN'),('id','not-an-id'),('payment_message','different code'),
                            ('plan','ultra'),('status','paid'),('amount_kopecks',1),
                            ('payment_url','https://www.donationalerts.com/r/'),
                            ('payment_url','https://www.donationalerts.com/r/denbroliik/other')]:
            order=self.order();order[field]=value
            with self.subTest(field=field,value=value),patch.object(cloud_account,'request',return_value=order):
                with self.assertRaisesRegex(ValueError,'неверный заказ'):billing.create_order('elite')

    def test_signed_out_never_queries_or_opens_payment(self):
        with patch.object(cloud_account,'state',return_value=None),patch.object(cloud_account,'request') as request:
            self.assertFalse(billing.account_status()['enabled']);request.assert_not_called()

    def test_order_check_and_cancel_do_not_allow_arbitrary_paths(self):
        with patch.object(cloud_account,'request') as request:
            for function in (billing.check_order,billing.cancel_order):
                with self.assertRaises(ValueError):function('../other-account')
            request.assert_not_called()

    def test_payment_status_must_belong_to_the_requested_order(self):
        key=str(uuid.uuid4())
        for response in ({'id':str(uuid.uuid4()),'plan':'elite','status':'paid'},
                         {'id':key,'plan':'elite','status':'unknown'},
                         {'id':key,'plan':'made-up','status':'paid'}):
            with patch.object(cloud_account,'request',return_value=response):
                with self.assertRaisesRegex(ValueError,'неверный статус'):billing.check_order(key)


class AndroidBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_google_button_launches_browser_and_recovers_transient_poll_failure(self):
        from App.settings.account import cloud as ui
        page=Mock()
        pending={'browser_url':'https://xopilot.by/api/v1/auth/google/open/synthetic'}
        with patch.object(cloud_account,'state',return_value=None), \
                patch.object(cloud_account,'begin_google',return_value=pending) as begin, \
                patch.object(cloud_account,'poll_google',side_effect=[cloud_account.CloudError('connection_failed'),True]) as poll, \
                patch.object(cloud_account,'cancel_google') as cancel, \
                patch.object(external_browser,'open_external',new=AsyncMock()) as launch, \
                patch.object(ui.asyncio,'sleep',new=AsyncMock()) as sleep:
            card=ui.build_cloud_card(page)
            def controls(control):
                yield control
                for child in getattr(control,'controls',[]) or []:yield from controls(child)
                child=getattr(control,'content',None)
                if child is not None and not isinstance(child,str):yield from controls(child)
            google=next(control for control in controls(card) if getattr(control,'content',None)=='Продолжить с Google')
            google.on_click(None)
            function,*arguments=page.run_task.call_args.args
            await function(*arguments)
            begin.assert_called_once_with(link=False)
            launch.assert_awaited_once_with(pending['browser_url'])
            self.assertEqual(poll.call_count,2)
            sleep.assert_awaited_once_with(4)
            page.pop_dialog.assert_called_once()
            cancel.assert_called_once_with(pending)

    async def test_android_uses_native_browser_not_unmounted_url_launcher(self):
        url='https://xopilot.by/api/v1/auth/google/open/test?ticket=synthetic'
        with patch.object(external_browser,'is_android',return_value=True), \
                patch.object(mobile_runtime,'call_async',new=AsyncMock(return_value=True)) as launch:
            await external_browser.open_external(url)
            launch.assert_awaited_once_with('openBrowser',{'url':url})

    async def test_android_refuses_non_https_credentials_or_javascript(self):
        with patch.object(external_browser,'is_android',return_value=True), \
                patch.object(mobile_runtime,'call_async',new=AsyncMock()) as launch:
            for url in ('http://example.com','https://user:password@example.com','javascript:alert(1)'):
                with self.assertRaises(ValueError):await external_browser.open_external(url)
            launch.assert_not_called()


class PaymentInterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_dialog_keeps_pending_payment_and_refreshes_after_server_confirmation(self):
        from App.settings.account import billing as ui
        page=Mock(height=800,width=393)
        database=Mock();database.get_setting.return_value='RUB'
        order=CheckoutTests().order()
        account={'enabled':True,'plan':'micro','signed_in':True}
        with patch.object(ui,'get_db',return_value=database),patch.object(cloud_account,'state',return_value={'account_id':'qa'}),patch.object(billing,'currency',return_value='RUB'), \
                patch.object(billing,'account_status',return_value=account) as account_status, \
                patch.object(billing,'create_order',return_value=order) as create, \
                patch.object(billing,'check_order',side_effect=[{'status':'pending'},{'status':'paid'}]) as check, \
                patch.object(external_browser,'open_external',new=AsyncMock()) as browser:
            ui.open_billing(page)
            await page.run_task.call_args.args[0]()
            dialog=page.show_dialog.call_args.args[0]
            cards=dialog.content.controls[4]
            purchase=next(control for control in cards.controls[1].content.controls
                          if getattr(control,'content',None)=='Оформить на месяц')
            self.assertFalse(purchase.disabled)
            purchase.on_click(None)
            function,*arguments=page.run_task.call_args.args
            await function(*arguments)
            create.assert_called_once_with('elite')
            payment_dialog=page.show_dialog.call_args.args[0]
            await payment_dialog.content.controls[6].on_click(None)
            browser.assert_awaited_once_with(order['payment_url'])
            await payment_dialog.content.controls[7].on_click(None)
            page.pop_dialog.assert_not_called()
            await payment_dialog.content.controls[7].on_click(None)
            page.pop_dialog.assert_called_once()
            self.assertEqual(account_status.call_count,2)
            self.assertEqual(check.call_count,2)

    async def test_closed_dialog_never_reappears_when_order_request_finishes(self):
        from App.settings.account import billing as ui
        page=Mock(height=800,width=393);database=Mock();database.get_setting.return_value='RUB'
        order=CheckoutTests().order()
        ready=asyncio.Event();release=asyncio.Event();created=[]
        async def slow(function,*args):
            if function is billing.create_order:
                created.append(args)
                ready.set();await release.wait();return order
            return function(*args)
        with patch.object(ui,'get_db',return_value=database), \
             patch.object(cloud_account,'state',return_value={'account_id':'qa'}), \
             patch.object(billing,'currency',return_value='RUB'), \
             patch.object(billing,'account_status',return_value={'enabled':True,'plan':'micro','signed_in':True}), \
             patch.object(ui.asyncio,'to_thread',side_effect=slow):
            ui.open_billing(page);await page.run_task.call_args.args[0]()
            dialog=page.show_dialog.call_args.args[0]
            purchase=next(c for c in dialog.content.controls[4].controls[1].content.controls
                          if getattr(c,'content',None)=='Оформить на месяц')
            purchase.on_click(None)
            function,*arguments=page.run_task.call_args.args
            task=asyncio.create_task(function(*arguments));await ready.wait()
            await function(*arguments)
            dialog.actions[0].on_click(None);release.set();await task
            self.assertEqual(page.show_dialog.call_count,1)
            self.assertEqual(len(created),1)

    async def test_automatic_confirmation_refreshes_without_cancelling_itself(self):
        from App.settings.account import billing as ui
        page=Mock(height=800,width=393);database=Mock();database.get_setting.return_value='RUB'
        order=CheckoutTests().order()
        with patch.object(ui,'get_db',return_value=database), \
             patch.object(cloud_account,'state',return_value={'account_id':'qa'}), \
             patch.object(billing,'currency',return_value='RUB'), \
             patch.object(billing,'account_status',side_effect=[{'enabled':True,'plan':'micro','signed_in':True},
                 {'enabled':True,'plan':'elite','signed_in':True,'expires_at':2000000000}]), \
             patch.object(billing,'create_order',return_value=order), \
             patch.object(billing,'check_order',return_value={'status':'paid'}) as check, \
             patch.object(ui.asyncio,'sleep',new=AsyncMock()):
            ui.open_billing(page);await page.run_task.call_args.args[0]()
            dialog=page.show_dialog.call_args.args[0]
            purchase=next(c for c in dialog.content.controls[4].controls[1].content.controls
                          if getattr(c,'content',None)=='Оформить на месяц')
            purchase.on_click(None)
            function,*arguments=page.run_task.call_args.args
            await function(*arguments)
            monitor=page.run_task.call_args.args[0]
            await monitor()
            check.assert_called_once_with(order['id'])
            page.pop_dialog.assert_called_once()
            self.assertIn('Zephyr Elite',dialog.content.controls[0].value)
            self.assertIn('активирована',dialog.content.controls[5].value)

    async def test_active_plan_prevents_accidental_second_plan_order(self):
        from App.settings.account import billing as ui
        page=Mock(height=800,width=393);database=Mock();database.get_setting.return_value='RUB'
        with patch.object(ui,'get_db',return_value=database), \
             patch.object(cloud_account,'state',return_value={'account_id':'qa'}), \
             patch.object(billing,'currency',return_value='RUB'), \
             patch.object(billing,'account_status',return_value={'enabled':True,'plan':'elite','signed_in':True}):
            ui.open_billing(page);await page.run_task.call_args.args[0]()
            cards=page.show_dialog.call_args.args[0].content.controls[4]
            buttons=[next(c for c in card.content.controls if isinstance(c,ft.FilledButton)) for card in cards.controls[1:]]
            self.assertFalse(buttons[0].disabled)
            self.assertTrue(buttons[1].disabled);self.assertTrue(buttons[2].disabled)

    async def test_account_failure_is_not_presented_as_a_free_subscription(self):
        from App.settings.account import billing as ui
        page=Mock(height=800,width=393);database=Mock();database.get_setting.return_value='RUB'
        with patch.object(ui,'get_db',return_value=database), \
             patch.object(cloud_account,'state',return_value={'account_id':'qa'}), \
             patch.object(billing,'currency',return_value='RUB'), \
             patch.object(billing,'account_status',side_effect=cloud_account.CloudError('connection_failed')):
            ui.open_billing(page);await page.run_task.call_args.args[0]()
            dialog=page.show_dialog.call_args.args[0]
            self.assertEqual(dialog.content.controls[0].value,'Не удалось загрузить подписку')
            self.assertTrue(dialog.content.controls[-1].visible)
            self.assertTrue(all(next(c for c in card.content.controls if isinstance(c,ft.FilledButton)).disabled
                                for card in dialog.content.controls[4].controls[1:]))
