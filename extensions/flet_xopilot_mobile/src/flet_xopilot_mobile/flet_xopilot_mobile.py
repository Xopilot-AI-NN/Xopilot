"""Private platform bridge. Construct once inside the Flet page callback."""
import flet as ft


@ft.control("XopilotMobile")
class XopilotMobile(ft.Service):
    on_metrics: ft.ControlEventHandler | None = None

    async def call(self, method, arguments=None, timeout=600):
        return await self._invoke_method(method, arguments or {}, timeout=timeout)
