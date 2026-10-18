"""Файл: /App/services/desktop_barge_in.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Перебивание Live на Linux через отдельный источник PipeWire WebRTC AEC.
          Не меняет устройства системы по умолчанию; узлы живут только до закрытия Live.
"""
import json
import os
import selectors
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import CancelledError
from .live_audio import SpeechSegmenter, FRAME_MS, check_live_audio


class DesktopBargeIn:
    def __init__(self):
        self.process = None
        self.name = 'xopilot_aec_' + uuid.uuid4().hex
        self._lock = threading.Lock()
        if not sys.platform.startswith('linux') or not all(shutil.which(c) for c in ('pw-cli','pactl','parec')):
            raise RuntimeError('Для перебивания голосом нужен PipeWire с WebRTC AEC; используйте кнопку «Перебить»')
        from .devices import selected_audio_device
        if any(selected_audio_device(kind) is not None for kind in ('input','output')):
            raise RuntimeError('Для перебивания голосом выберите системные аудиоустройства по умолчанию')
        source=self._command(['pactl','get-default-source']).strip()
        sink=self._command(['pactl','get-default-sink']).strip()
        if not source or not sink or source.endswith('.monitor'):
            raise RuntimeError('Выберите системный микрофон для перебивания голосом')
        # monitor.mode removes sound from the normal output, including our TTS.
        # No playback rerouting and no changes to system default sources/sinks.
        arguments=('{ audio.rate=48000 audio.channels=1 monitor.mode=true '
            'capture.props={ target.object='+json.dumps(source)+' node.passive=true } '
            'playback.props={ target.object='+json.dumps(sink)+' node.passive=true } '
            'source.props={ node.name='+self.name+' node.description="Xopilot Live AEC" } }')
        self.process=subprocess.Popen(['pw-cli','-m','load-module','libpipewire-module-echo-cancel',arguments],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if self.process.poll() is not None:break
                if self.name in self._command(['pactl','list','short','sources']):return
                time.sleep(.05)
            raise RuntimeError('PipeWire не создал источник с подавлением эха; доступна кнопка «Перебить»')
        except BaseException:
            self.close();raise

    @staticmethod
    def _command(arguments):
        return subprocess.check_output(arguments,text=True,timeout=3,stderr=subprocess.DEVNULL)

    def record(self, cancelled, on_speech_start):
        """Preserve the interruption's onset and whole utterance after cancelling TTS."""
        check_live_audio()
        with self._lock:
            if cancelled.is_set():raise CancelledError()
            if self.process is None or self.process.poll() is not None:raise RuntimeError('Источник AEC закрыт')
            recorder=subprocess.Popen(['parec','--raw','--format=s16le','--rate=16000','--channels=1',
                '--latency-msec=30','--device='+self.name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            selector=selectors.DefaultSelector();selector.register(recorder.stdout,selectors.EVENT_READ)
            segment=SpeechSegmenter(16000)
            pending=bytearray();notified=False;last_frame=time.monotonic()
            frame_bytes=16000*FRAME_MS//1000*2
            try:
                while not segment.finished:
                    if cancelled.is_set():raise CancelledError()
                    if not selector.select(.05):
                        if recorder.poll() is not None or time.monotonic()-last_frame>3:
                            raise RuntimeError('Источник AEC перестал передавать звук')
                        continue
                    data=os.read(recorder.stdout.fileno(),8192)
                    if not data:raise RuntimeError('Источник AEC завершил запись')
                    last_frame=time.monotonic();pending.extend(data)
                    while len(pending)>=frame_bytes and not segment.finished:
                        frame=bytes(pending[:frame_bytes]);del pending[:frame_bytes]
                        segment.feed(frame)
                        if segment.started and not notified:
                            notified=True
                            if not cancelled.is_set():on_speech_start()
                if cancelled.is_set():raise CancelledError()
                return segment.wav_bytes()
            finally:
                selector.close()
                recorder.terminate()
                try:recorder.wait(timeout=2)
                except subprocess.TimeoutExpired:recorder.kill();recorder.wait()
                recorder.stdout.close()

    def close(self):
        process,self.process=self.process,None
        if process is not None:
            process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait()
