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
        await call_async('openBrowser', {'url': url})
    else:
        import flet as ft
        await ft.UrlLauncher().launch_url(url, mode=ft.LaunchMode.EXTERNAL_APPLICATION,
                                         web_only_window_name='_blank')
