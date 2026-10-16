"""Open authentication/payment pages in the system browser, never a WebView."""
from urllib.parse import urlsplit
from .platforms import is_android


async def open_external(url):
    parts = urlsplit(url)
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Неверный адрес браузера')
    if is_android():
        if parts.scheme != 'https':
            raise ValueError('Для Android-входа требуется HTTPS')
        from .mobile_runtime import call_async
        import asyncio
        try:
            result=await asyncio.wait_for(call_async('openBrowser', {'url': url}),timeout=5)
            if result is False:raise RuntimeError('Браузер не открылся')
        except Exception:
            import flet as ft
            if not await ft.UrlLauncher().launch_url(url,mode=ft.LaunchMode.EXTERNAL_APPLICATION):
                raise RuntimeError('Не удалось открыть браузер. Проверьте, установлен ли браузер по умолчанию.')
    else:
        import flet as ft
        await ft.UrlLauncher().launch_url(url, mode=ft.LaunchMode.EXTERNAL_APPLICATION,
                                         web_only_window_name='_blank')
