"""Файл: /App/app/tasks/turn_narration.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Пояснения инструментов и итог задачи в одном сохранённом сообщении.
"""
import asyncio


class TurnNarration:
    def __init__(self, save, update, elapsed):
        self.save, self.update, self.elapsed = save, update, elapsed
        self.message_id = None
        self.text = ''
        self._lock = asyncio.Lock()
        self._finished = False

    def preview(self, text):
        return self.text + ('\n\n' if self.text else '') + str(text)

    async def append(self, text):
        async with self._lock:
            if self._finished:
                return self.message_id, self.text, len(self.text)
            return await self._store(self.preview(text))

    async def finish(self, text, files=None, seconds=None):
        async with self._lock:
            if self._finished:
                return self.message_id, self.text, len(self.text)
            answer=('<!-- xopilot:answer -->\n' if self.text.startswith('<!-- xopilot:progress -->\n') else '')+str(text)
            result = await self._store(self.preview(answer), files, seconds)
            self._finished = True
            return result

    async def _store(self, text, files=None, seconds=None):
        start = len(self.text)
        if self.message_id is None:
            self.message_id = await asyncio.to_thread(self.save, text,
                attachments=files, elapsed_seconds=seconds)
        else:
            updated = await asyncio.to_thread(self.update, self.message_id, text,
                **({'attachments': files} if files is not None else {}))
            if not updated:
                raise RuntimeError('Сообщение задачи удалено. Пояснения не сохранены.')
            if seconds is not None:
                await asyncio.to_thread(self.elapsed, self.message_id, seconds)
        self.text = text
        return self.message_id, self.text, start
