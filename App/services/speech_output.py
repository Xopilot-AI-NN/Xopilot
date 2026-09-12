"""
Файл: App/services/speech_output.py
Разработчик: DenBroLiik
Описание: Локальная озвучка через eSpeak NG, Windows SAPI или macOS say.
    Текст передаётся через stdin без shell; отмена завершает процесс озвучки.
"""

import base64
import json
import platform
import re
import shutil
import subprocess
import time
from concurrent.futures import CancelledError


_WINDOWS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice = $speaker.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $request.language
    } | Select-Object -First 1
    if ($null -eq $voice) { throw 'Install a system speech voice for the requested language.' }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $speaker.SetOutputToDefaultAudioDevice()
    $speaker.Speak($request.text)
} finally { $speaker.Dispose() }
"""


def spoken_text(text):
    """Убирает разметку, которую не нужно проговаривать как служебные символы."""
    text = re.sub(r"```.*?```", "Код приведён в чате.", text, flags=re.DOTALL)
    text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*>]\s+)", "", text)
    text = re.sub(r"[`*_]", "", text)
    return text.strip()


class SpeechOutput:
    def __init__(self):
        self.system = platform.system()
        self.executable = shutil.which("espeak-ng") or shutil.which("espeak")
        if self.executable:
            self.backend = "espeak"
        elif self.system == "Windows" and shutil.which("powershell.exe"):
            self.executable = shutil.which("powershell.exe")
            self.backend = "sapi"
        elif self.system == "Darwin" and shutil.which("say"):
            self.executable = shutil.which("say")
            self.backend = "say"
        else:
            raise RuntimeError("Не найден голос для Live. Установите eSpeak NG и добавьте его в PATH.")

    def _command(self, text):
        language = "ru" if re.search(r"[А-Яа-яЁё]", text) else "en"
        if self.backend == "espeak":
            return [self.executable, "-b", "1", "-v", language, "-s", "175", "--stdin"], text.encode("utf-8")
        if self.backend == "sapi":
            script = base64.b64encode(_WINDOWS_SCRIPT.encode("utf-16-le")).decode("ascii")
            return [self.executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", script], json.dumps(
                {"text": text, "language": language}, ensure_ascii=False,
            ).encode("utf-8")
        return [self.executable, "-v", "Milena" if language == "ru" else "Samantha"], text.encode("utf-8")

    def speak(self, text, cancelled):
        if cancelled.is_set():
            raise CancelledError()
        text = spoken_text(text)
        if not text:
            return
        command, payload = self._command(text)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if self.system == "Windows" else 0,
        )
        deadline = time.monotonic() + 120
        try:
            while True:
                if cancelled.is_set():
                    raise CancelledError()
                if time.monotonic() >= deadline:
                    raise RuntimeError("Озвучка не завершилась вовремя. Перезапустите Live.")
                try:
                    _, stderr = process.communicate(input=payload, timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    payload = None
            if cancelled.is_set():
                raise CancelledError()
            if process.returncode:
                detail = stderr.decode("utf-8", errors="replace").strip()[-300:]
                raise RuntimeError(f"Не удалось озвучить ответ. Проверьте системный голос и устройство вывода. {detail}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
