"""Файл: /App/services/mobile_litert.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Мост Android LiteRT-LM с явным окном контекста и отменой генерации.
"""
"""The subset of the LiteRT Python API used by Xopilot, backed by Android JNI.

No desktop ctypes library is loaded. The official Kotlin SDK owns all engines
and conversations. Contents/history use the same format as the desktop client.
"""
import base64
import time
from types import SimpleNamespace
from . import mobile_runtime as runtime


class Backend:
    @staticmethod
    def CPU(): return 'cpu'

    @staticmethod
    def GPU(): return 'gpu'


class Capabilities:
    def __init__(self, path):
        self.input_modalities = SimpleNamespace(**runtime.capabilities(path))

    def __enter__(self): return self
    def __exit__(self, *args): return False


class _Bytes:
    def __init__(self, data, kind):
        self.data, self.kind = data, kind

    def to_json(self):
        return {'type': self.kind, 'data': base64.b64encode(self.data).decode('ascii')}


class Content:
    @staticmethod
    def ImageBytes(data): return _Bytes(data, 'image')

    @staticmethod
    def AudioBytes(data): return _Bytes(data, 'audio')


class Contents:
    def __init__(self, parts): self.parts = parts

    @classmethod
    def of(cls, *parts): return cls(parts)

    def to_json(self):
        return [{'type': 'text', 'text': part} if isinstance(part, str) else part.to_json()
                for part in self.parts]


class SamplerConfig:
    def __init__(self, temperature): self.temperature = temperature


class ThinkingConfig:
    def __init__(self, enable_thinking): self.enable_thinking = enable_thinking


class Engine:
    def __init__(self, path, *, backend, cache_dir, vision_backend=None, audio_backend=None, max_num_tokens=4096):
        self.closed = False
        self.max_num_tokens = max_num_tokens
        runtime.call('load', dict(path=str(path), backend=backend, cache=cache_dir, context=max_num_tokens,
                                 vision=vision_backend is not None, audio=audio_backend is not None))

    def create_conversation(self, *, system_message, messages=None, sampler_config=None, thinking_config=None, max_output_tokens=None):
        if self.closed: raise RuntimeError('Модель закрыта')
        args = dict(system=system_message, messages=messages or [])
        if sampler_config is not None: args['temperature'] = sampler_config.temperature
        if thinking_config is not None: args['thinking'] = thinking_config.enable_thinking
        if max_output_tokens is not None: args['max_output_tokens'] = max_output_tokens
        return Conversation(runtime.call('openConversation', args))

    def close(self):
        if not self.closed:
            runtime.call('closeAll')
            self.closed = True


class Conversation:
    def __init__(self, identity): self.identity, self.closed = identity, False
    def __enter__(self): return self
    def __exit__(self, *args): self.close(); return False

    def send_message(self, message):
        if self.closed: raise RuntimeError('Разговор закрыт')
        if isinstance(message, Contents): message = message.to_json()
        elif isinstance(message, dict): message = message['content']
        answer = runtime.call('send', {'id': self.identity, 'content': message})
        return {'content': [{'type': 'text', 'text': answer}]}

    def send_message_async(self, message):
        if self.closed: raise RuntimeError('Разговор закрыт')
        if isinstance(message, Contents): message = message.to_json()
        elif isinstance(message, dict): message = message['content']
        runtime.call('streamStart', {'id': self.identity, 'content': message})
        while True:
            state = runtime.call('streamPoll', {'id': self.identity})
            for text in state.get('chunks', []):
                yield {'content': [{'type': 'text', 'text': text}]}
            if state.get('error'):
                raise RuntimeError(state['error'])
            if state.get('done'):
                break
            time.sleep(.05)

    def cancel_process(self):
        if not self.closed: runtime.call('cancel', {'id': self.identity})

    def close(self):
        if not self.closed:
            runtime.call('closeConversation', {'id': self.identity})
            self.closed = True
