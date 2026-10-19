"""Файл: /App/services/conversation_cache.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Один живой KV-контекст; переиспользование только точного продолжения чата.
"""
from contextlib import contextmanager
from copy import deepcopy


class ConversationCache:
    """Caller owns the engine lock. Never caches answers or private conversations."""

    def __init__(self):
        self.session = None
        self.key = None
        self.history = None
        self.hits = 0
        self.misses = 0

    def clear(self):
        session, self.session = self.session, None
        self.key = self.history = None
        if session is not None:
            session.close()

    @contextmanager
    def acquire(self, key, history, create):
        reusable = key is not None
        if not reusable:
            self.clear()
            self.misses += 1
            with create() as session:
                yield session
            return
        if reusable and self.session is not None and key == self.key and history == self.history:
            self.hits += 1
        else:
            self.clear()
            self.misses += 1
            self.session = create()
            self.key = key
        try:
            yield self.session
        except BaseException:
            self.clear()  # Cancellation/error may have partially advanced the native KV state.
            raise
        finally:
            if not reusable:
                self.clear()

    def remember(self, history, current, answer):
        if self.session is not None and self.key is not None:
            self.history = deepcopy([*history, {'role': 'user', 'content': current},
                {'role': 'model', 'content': [{'type': 'text', 'text': answer}]}])
