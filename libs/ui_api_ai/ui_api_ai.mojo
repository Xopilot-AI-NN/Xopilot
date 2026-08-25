"""
Файл: /libs/ui_api_ai.mojo
Разработчик: [DenBroLiik, Claude]
Версия: 2.0.0
Описание: API для связи с ИИ моделями
    и получения от них данных для отображения в интерфейсе.

Поддерживаемые провайдеры:
    - Ollama             (gemma4:12b, qwen и т.д.)
    - OpenAI-совместимый (кастомный gemma_server.py, LM Studio, vLLM)
    - Anthropic          (Claude API)

Мультимодальность:
    - Текст     — все провайдеры
    - Изображения — Ollama vision, OpenAI-compat, Anthropic
    - Аудио     — OpenAI-compat (gemma_server.py с нативным аудио)
    - Видео     — OpenAI-compat (кадры как изображения)
"""

from python import Python, PythonObject
from collections import List


# ══════════════════════════════════════════════════════
#  ПРОВАЙДЕРЫ
# ══════════════════════════════════════════════════════

alias OLLAMA    = "ollama"
alias OPENAI    = "openai"
alias ANTHROPIC = "anthropic"


# ══════════════════════════════════════════════════════
#  ТИПЫ КОНТЕНТА
# ══════════════════════════════════════════════════════

alias KIND_TEXT  = "text"
alias KIND_IMAGE = "image"
alias KIND_AUDIO = "audio"
alias KIND_VIDEO = "video"


# ══════════════════════════════════════════════════════
#  СТРУКТУРЫ ДАННЫХ
# ══════════════════════════════════════════════════════

@value
struct ContentPart:
    """
    Одна часть сообщения — текст, изображение, аудио или видео.

    Для текста:   kind=KIND_TEXT,  text="..."
    Для image:    kind=KIND_IMAGE, data=<base64>, mime="image/jpeg"
    Для audio:    kind=KIND_AUDIO, data=<base64>, mime="audio/wav"
    Для video:    kind=KIND_VIDEO, data=<base64>, mime="video/mp4"
    """
    var kind: String
    var text: String    # только для KIND_TEXT
    var data: String    # base64 для image/audio/video
    var mime: String    # MIME тип медиа

    fn __init__(inout self, kind: String, text: String = "", data: String = "", mime: String = ""):
        self.kind = kind
        self.text = text
        self.data = data
        self.mime = mime

    fn is_media(self) -> Bool:
        return self.kind != KIND_TEXT


@value
struct Message:
    """
    Сообщение в чате. Может содержать несколько частей (мультимодально).

    Простой текст:
        Message("user", parts=[text_part("Привет")])

    С изображением:
        Message("user", parts=[
            image_part_from_file("/path/img.jpg"),
            text_part("Что на фото?"),
        ])
    """
    var role: String
    var parts: List[ContentPart]

    fn __init__(inout self, role: String, parts: List[ContentPart]):
        self.role = role
        self.parts = parts

    fn text_only(self) -> Bool:
        """True — сообщение содержит только текст."""
        for i in range(len(self.parts)):
            if self.parts[i].is_media():
                return False
        return True

    fn plain_text(self) -> String:
        """Объединить все текстовые части в одну строку."""
        var result = String("")
        for i in range(len(self.parts)):
            if self.parts[i].kind == KIND_TEXT:
                result += self.parts[i].text
        return result


@value
struct ChatResponse:
    """Ответ от модели."""
    var content: String
    var model: String
    var ok: Bool
    var error: String

    fn __init__(inout self, content: String, model: String):
        self.content = content
        self.model = model
        self.ok = True
        self.error = ""

    @staticmethod
    fn err(msg: String) -> Self:
        var r = Self("", "")
        r.ok = False
        r.error = msg
        return r


@value
struct AIConfig:
    var provider: String
    var model: String
    var base_url: String
    var api_key: String
    var timeout: Int

    fn __init__(
        inout self,
        provider: String,
        model: String,
        base_url: String = "http://localhost:11434",
        api_key: String = "",
        timeout: Int = 60,
    ):
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout


# ══════════════════════════════════════════════════════
#  ХЕЛПЕРЫ ДЛЯ СОЗДАНИЯ ЧАСТЕЙ
# ══════════════════════════════════════════════════════

fn text_part(content: String) -> ContentPart:
    return ContentPart(KIND_TEXT, text=content)


fn image_part_base64(b64: String, mime: String = "image/jpeg") -> ContentPart:
    """Изображение из base64 строки."""
    return ContentPart(KIND_IMAGE, data=b64, mime=mime)


fn audio_part_base64(b64: String, mime: String = "audio/wav") -> ContentPart:
    """Аудио из base64 строки."""
    return ContentPart(KIND_AUDIO, data=b64, mime=mime)


fn image_part_from_file(path: String) raises -> ContentPart:
    """Читает файл изображения и возвращает base64 ContentPart."""
    var base64 = Python.import_module("base64")
    var builtins = Python.import_module("builtins")
    var f = builtins.open(path, "rb")
    var raw = f.read()
    f.close()
    var b64 = str(base64.b64encode(raw).decode("utf-8"))
    # Определяем MIME по расширению
    var mime = String("image/jpeg")
    if path.endswith(".png"):
        mime = "image/png"
    elif path.endswith(".gif"):
        mime = "image/gif"
    elif path.endswith(".webp"):
        mime = "image/webp"
    return ContentPart(KIND_IMAGE, data=b64, mime=mime)


fn audio_part_from_file(path: String) raises -> ContentPart:
    """Читает аудио файл и возвращает base64 ContentPart."""
    var base64 = Python.import_module("base64")
    var builtins = Python.import_module("builtins")
    var f = builtins.open(path, "rb")
    var raw = f.read()
    f.close()
    var b64 = str(base64.b64encode(raw).decode("utf-8"))
    var mime = String("audio/wav")
    if path.endswith(".mp3"):
        mime = "audio/mpeg"
    elif path.endswith(".ogg"):
        mime = "audio/ogg"
    return ContentPart(KIND_AUDIO, data=b64, mime=mime)


fn audio_part_from_numpy(array: PythonObject, sample_rate: Int = 16000) raises -> ContentPart:
    """
    Конвертирует numpy float32 массив в WAV base64 ContentPart.
    Используется для живого микрофонного ввода.
    """
    var io = Python.import_module("io")
    var sf = Python.import_module("soundfile")
    var base64 = Python.import_module("base64")

    var buf = io.BytesIO()
    sf.write(buf, array, sample_rate, format="WAV", subtype="PCM_16")
    buf.seek(0)
    var b64 = str(base64.b64encode(buf.read()).decode("utf-8"))
    return ContentPart(KIND_AUDIO, data=b64, mime="audio/wav")


# ══════════════════════════════════════════════════════
#  OLLAMA КЛИЕНТ (текст + изображения)
# ══════════════════════════════════════════════════════

struct OllamaClient:
    """
    Ollama поддерживает изображения через поле "images" в сообщении.
    Аудио нативно не поддерживается — используй OpenAI-compat обёртку.
    """
    var base_url: String
    var model: String
    var timeout: Int

    fn __init__(inout self, base_url: String, model: String, timeout: Int = 60):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    fn _build_payload(self, messages: List[Message]) raises -> PythonObject:
        var py_msgs = Python.evaluate("[]")

        for i in range(len(messages)):
            var msg = messages[i]
            var d = Python.evaluate("{}")
            d["role"] = msg.role

            # Ollama: текст в "content", изображения в "images"
            var text = String("")
            var images = Python.evaluate("[]")

            for j in range(len(msg.parts)):
                var part = msg.parts[j]
                if part.kind == KIND_TEXT:
                    text += part.text
                elif part.kind == KIND_IMAGE:
                    _ = images.append(part.data)  # raw base64 без data URI

            d["content"] = text
            if len(Python.evaluate("list")(images)) > 0:
                d["images"] = images

            _ = py_msgs.append(d)

        var payload = Python.evaluate("{}")
        payload["model"]    = self.model
        payload["messages"] = py_msgs
        payload["stream"]   = False
        return payload

    fn chat(self, messages: List[Message]) raises -> ChatResponse:
        var requests = Python.import_module("requests")
        try:
            var resp = requests.post(
                self.base_url + "/api/chat",
                json=self._build_payload(messages),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            var data = resp.json()
            return ChatResponse(str(data["message"]["content"]), self.model)
        except e:
            return ChatResponse.err("Ollama: " + str(e))

    fn list_models(self) raises -> List[String]:
        var requests = Python.import_module("requests")
        var result = List[String]()
        try:
            var resp = requests.get(self.base_url + "/api/tags", timeout=5)
            var models = resp.json()["models"]
            for i in range(len(models)):
                result.append(str(models[i]["name"]))
        except:
            pass
        return result

    fn is_alive(self) raises -> Bool:
        var requests = Python.import_module("requests")
        try:
            var resp = requests.get(self.base_url, timeout=3)
            return int(resp.status_code) == 200
        except:
            return False


# ══════════════════════════════════════════════════════
#  OPENAI-СОВМЕСТИМЫЙ КЛИЕНТ (текст + изображения + аудио)
# ══════════════════════════════════════════════════════

struct OpenAIClient:
    """
    Поддерживает полную мультимодальность:
    - Текст
    - Изображения  → {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    - Аудио        → {"type": "input_audio", "input_audio": {"data": "...", "format": "wav"}}

    Для нативного аудио Gemma 4 12B — подключай свой gemma_server.py
    через make_openai_compat("http://localhost:8080", "gemma-4-12b")
    """
    var base_url: String
    var model: String
    var api_key: String
    var timeout: Int

    fn __init__(
        inout self,
        base_url: String,
        model: String,
        api_key: String = "",
        timeout: Int = 60,
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    fn _build_content_part(self, part: ContentPart) raises -> PythonObject:
        var d = Python.evaluate("{}")

        if part.kind == KIND_TEXT:
            d["type"] = "text"
            d["text"] = part.text

        elif part.kind == KIND_IMAGE:
            d["type"] = "image_url"
            var img = Python.evaluate("{}")
            img["url"] = "data:" + part.mime + ";base64," + part.data
            d["image_url"] = img

        elif part.kind == KIND_AUDIO:
            # Формат для OpenAI Audio / кастомного gemma_server
            d["type"] = "input_audio"
            var audio = Python.evaluate("{}")
            audio["data"]   = part.data
            # Извлекаем формат из mime (audio/wav → wav)
            var fmt = part.mime
            if "wav" in fmt:
                audio["format"] = "wav"
            elif "mp3" in fmt or "mpeg" in fmt:
                audio["format"] = "mp3"
            else:
                audio["format"] = "wav"
            d["input_audio"] = audio

        return d

    fn _build_payload(self, messages: List[Message]) raises -> PythonObject:
        var py_msgs = Python.evaluate("[]")

        for i in range(len(messages)):
            var msg = messages[i]
            var d = Python.evaluate("{}")
            d["role"] = msg.role

            if msg.text_only():
                # Простой текст — передаём строкой (совместимость)
                d["content"] = msg.plain_text()
            else:
                # Мультимодальный — массив частей
                var parts = Python.evaluate("[]")
                for j in range(len(msg.parts)):
                    _ = parts.append(self._build_content_part(msg.parts[j]))
                d["content"] = parts

            _ = py_msgs.append(d)

        var payload = Python.evaluate("{}")
        payload["model"]    = self.model
        payload["messages"] = py_msgs
        return payload

    fn _headers(self) raises -> PythonObject:
        var h = Python.evaluate("{}")
        h["Content-Type"] = "application/json"
        if len(self.api_key) > 0:
            h["Authorization"] = "Bearer " + self.api_key
        return h

    fn chat(self, messages: List[Message]) raises -> ChatResponse:
        var requests = Python.import_module("requests")
        try:
            var resp = requests.post(
                self.base_url + "/v1/chat/completions",
                json=self._build_payload(messages),
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            var data = resp.json()
            var content = str(data["choices"][0]["message"]["content"])
            return ChatResponse(content, self.model)
        except e:
            return ChatResponse.err("OpenAI-compat: " + str(e))


# ══════════════════════════════════════════════════════
#  ANTHROPIC КЛИЕНТ (текст + изображения)
# ══════════════════════════════════════════════════════

struct AnthropicClient:
    """
    Anthropic поддерживает текст и изображения.
    Аудио через Anthropic API пока недоступно.
    """
    var model: String
    var api_key: String
    var timeout: Int

    fn __init__(inout self, model: String, api_key: String, timeout: Int = 60):
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    fn _build_content_part(self, part: ContentPart) raises -> PythonObject:
        var d = Python.evaluate("{}")

        if part.kind == KIND_TEXT:
            d["type"] = "text"
            d["text"] = part.text

        elif part.kind == KIND_IMAGE:
            d["type"] = "image"
            var src = Python.evaluate("{}")
            src["type"]       = "base64"
            src["media_type"] = part.mime
            src["data"]       = part.data
            d["source"] = src

        return d

    fn chat(self, messages: List[Message]) raises -> ChatResponse:
        var requests = Python.import_module("requests")

        var system_text = String("")
        var py_msgs = Python.evaluate("[]")

        for i in range(len(messages)):
            var msg = messages[i]
            if msg.role == "system":
                system_text = msg.plain_text()
                continue

            var d = Python.evaluate("{}")
            d["role"] = msg.role

            if msg.text_only():
                d["content"] = msg.plain_text()
            else:
                var parts = Python.evaluate("[]")
                for j in range(len(msg.parts)):
                    _ = parts.append(self._build_content_part(msg.parts[j]))
                d["content"] = parts

            _ = py_msgs.append(d)

        var payload = Python.evaluate("{}")
        payload["model"]      = self.model
        payload["max_tokens"] = 2048
        payload["messages"]   = py_msgs
        if len(system_text) > 0:
            payload["system"] = system_text

        var headers = Python.evaluate("{}")
        headers["x-api-key"]        = self.api_key
        headers["anthropic-version"] = "2023-06-01"
        headers["content-type"]      = "application/json"

        try:
            var resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            var data = resp.json()
            return ChatResponse(str(data["content"][0]["text"]), self.model)
        except e:
            return ChatResponse.err("Anthropic: " + str(e))


# ══════════════════════════════════════════════════════
#  ГЛАВНЫЙ ФАСАД — XopilotAI
# ══════════════════════════════════════════════════════

struct XopilotAI:
    """
    Единый AI-интерфейс Xopilot для всех провайдеров.

    Примеры из Python/Flet:

        # Текст
        ai = make_ollama("gemma4:12b")
        resp = ai.send([msg("user", [text_part("Привет!")])])

        # Изображение
        parts = [image_part_from_file("/tmp/photo.jpg"), text_part("Что здесь?")]
        resp = ai.send([msg("user", parts)])

        # Аудио (через gemma_server.py)
        ai = make_openai_compat("http://localhost:8080", "gemma-4-12b")
        parts = [text_part("Транскрибируй:"), audio_part_from_file("/tmp/rec.wav")]
        resp = ai.send([msg("user", parts)])
    """
    var config: AIConfig

    fn __init__(inout self, config: AIConfig):
        self.config = config

    fn send(self, history: List[Message]) raises -> ChatResponse:
        if self.config.provider == OLLAMA:
            var c = OllamaClient(self.config.base_url, self.config.model, self.config.timeout)
            return c.chat(history)
        elif self.config.provider == OPENAI:
            var c = OpenAIClient(self.config.base_url, self.config.model, self.config.api_key, self.config.timeout)
            return c.chat(history)
        elif self.config.provider == ANTHROPIC:
            var c = AnthropicClient(self.config.model, self.config.api_key, self.config.timeout)
            return c.chat(history)
        else:
            return ChatResponse.err("Unknown provider: " + self.config.provider)

    fn models(self) raises -> List[String]:
        if self.config.provider == OLLAMA:
            var c = OllamaClient(self.config.base_url, self.config.model)
            return c.list_models()
        return List[String]()

    fn connected(self) raises -> Bool:
        if self.config.provider == OLLAMA:
            var c = OllamaClient(self.config.base_url, self.config.model)
            return c.is_alive()
        return len(self.config.api_key) > 0


# ══════════════════════════════════════════════════════
#  ФАБРИКИ
# ══════════════════════════════════════════════════════

fn make_ollama(model: String, base_url: String = "http://localhost:11434") -> XopilotAI:
    return XopilotAI(AIConfig(OLLAMA, model, base_url))

fn make_openai_compat(base_url: String, model: String, api_key: String = "") -> XopilotAI:
    return XopilotAI(AIConfig(OPENAI, model, base_url, api_key))

fn make_anthropic(model: String, api_key: String) -> XopilotAI:
    return XopilotAI(AIConfig(ANTHROPIC, model, "", api_key))

fn msg(role: String, parts: List[ContentPart]) -> Message:
    return Message(role, parts)
