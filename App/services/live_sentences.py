"""Файл: /App/services/live_sentences.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Сбор законченных фраз из потока модели для ранней озвучки Live.
"""
import re


class LiveSentences:
    def __init__(self):
        self.pending = ''

    def feed(self, text, *, final=False):
        self.pending += text
        parts = []
        # Wait for whitespace after punctuation: a token ending in a dot may
        # still be a decimal number. Preserve the last unfinished phrase.
        while match := re.search(r'[.!?…]+["»”\']*(?=\s)|\n+', self.pending):
            end = match.end()
            part, self.pending = self.pending[:end].strip(), self.pending[end:].lstrip()
            if part:
                parts.append(part)
        if final and self.pending.strip():
            parts.append(self.pending.strip())
            self.pending = ''
        return parts
