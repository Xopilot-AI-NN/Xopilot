// Подготавливаем файлы средствами WebView. Все данные остаются на устройстве.
// Кодеки предоставляет ОС. Объём, длительность и число кадров ограничены.
await (async () => {
  let objectUrl;
  let video;
  let audioContext;
  try {
    const request = await dioxus.recv();
    const binary = atob(request.data);
    const bytes = Uint8Array.from(binary, (character) =>
      character.charCodeAt(0),
    );
    const blob = new Blob([bytes], { type: request.mime });
    objectUrl = URL.createObjectURL(blob);
    const encode = (data) => {
      let binary = "";
      for (let offset = 0; offset < data.length; offset += 32768)
        binary += String.fromCharCode(...data.subarray(offset, offset + 32768));
      return btoa(binary);
    };
    // Каждая операция имеет собственный таймаут и удаляет обработчики.
    const waitFor = (element, event, action) =>
      new Promise((resolve, reject) => {
        const finish = (error) => {
          clearTimeout(timer);
          element.removeEventListener(event, ready);
          element.removeEventListener("error", failed);
          error ? reject(error) : resolve();
        };
        const ready = () => finish();
        const failed = () =>
          finish(new Error("Кодек этого файла недоступен в системе"));
        const timer = setTimeout(
          () => finish(new Error("Истекло время декодирования медиа")),
          10000,
        );
        element.addEventListener(event, ready, { once: true });
        element.addEventListener("error", failed, { once: true });
        action();
      });
    const result = { duration: 0, frames: [], audio: null, warning: "" };
    if (request.video) {
      video = document.createElement("video");
      video.muted = true;
      video.playsInline = true;
      video.preload = "auto";
      await waitFor(video, "loadeddata", () => {
        video.src = objectUrl;
        video.load();
      });
      result.duration = video.duration;
      if (
        !Number.isFinite(result.duration) ||
        result.duration <= 0 ||
        result.duration > 30
      )
        throw new Error(
          "Для анализа выберите видео длительностью до 30 секунд",
        );
      const canvas = document.createElement("canvas");
      const ratio = Math.min(
        1,
        1024 / Math.max(video.videoWidth, video.videoHeight),
      );
      canvas.width = Math.max(1, Math.round(video.videoWidth * ratio));
      canvas.height = Math.max(1, Math.round(video.videoHeight * ratio));
      const context = canvas.getContext("2d");
      const count = Math.min(4, Math.max(1, Math.ceil(result.duration)));
      for (let index = 0; index < count; index++) {
        const seconds =
          count === 1 ? 0 : ((result.duration - 0.05) * index) / (count - 1);
        if (Math.abs(video.currentTime - seconds) > 0.01)
          await waitFor(video, "seeked", () => {
            video.currentTime = seconds;
          });
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        result.frames.push({
          seconds,
          data: canvas.toDataURL("image/jpeg", 0.8).split(",")[1],
        });
      }
    }
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioContext();
      const decoded = await Promise.race([
        audioContext.decodeAudioData(bytes.buffer.slice(0)),
        new Promise((_, reject) =>
          setTimeout(
            () => reject(new Error("Истекло время декодирования звука")),
            10000,
          ),
        ),
      ]);
      if (
        !Number.isFinite(decoded.duration) ||
        decoded.duration <= 0 ||
        decoded.duration > 30
      )
        throw new Error(
          "Для анализа выберите аудио длительностью до 30 секунд",
        );
      result.duration = Math.max(result.duration, decoded.duration);
      // OfflineAudioContext смешивает каналы и пересчитывает частоту до
      // 16 кГц. WAV PCM16 подходит локальному LiteRT и совместимому API.
      const Offline =
        window.OfflineAudioContext || window.webkitOfflineAudioContext;
      const offline = new Offline(
        1,
        Math.ceil(decoded.duration * 16000),
        16000,
      );
      const source = offline.createBufferSource();
      source.buffer = decoded;
      source.connect(offline.destination);
      source.start();
      const mono = (await offline.startRendering()).getChannelData(0);
      const wav = new ArrayBuffer(44 + mono.length * 2);
      const view = new DataView(wav);
      const label = (offset, text) => {
        for (let i = 0; i < text.length; i++)
          view.setUint8(offset + i, text.charCodeAt(i));
      };
      label(0, "RIFF");
      view.setUint32(4, wav.byteLength - 8, true);
      label(8, "WAVE");
      label(12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, 16000, true);
      view.setUint32(28, 32000, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      label(36, "data");
      view.setUint32(40, mono.length * 2, true);
      for (let index = 0; index < mono.length; index++) {
        const value = Math.max(-1, Math.min(1, mono[index]));
        view.setInt16(
          44 + index * 2,
          value * (value < 0 ? 32768 : 32767),
          true,
        );
      }
      result.audio = encode(new Uint8Array(wav));
    } catch (error) {
      if (!request.video) throw error;
      result.warning =
        "Звуковая дорожка недоступна для декодирования. Анализируются только выбранные кадры.";
    }
    dioxus.send({ ok: true, result });
  } catch (error) {
    dioxus.send({ ok: false, error: String(error.message || error) });
  } finally {
    if (video) {
      video.removeAttribute("src");
      video.load();
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    if (audioContext) await audioContext.close().catch(() => {});
  }
})();
