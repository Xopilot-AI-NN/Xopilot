const automatic = false;
// Запись mono PCM локально. Поток микрофона закрывается при остановке,
// ошибке, уходе со страницы и по ограничению длительности.
let stream;
let context;
let source;
let processor;
let timer;
let stop;
let onVisibility;
let cancelled = false;
dioxus
  .recv()
  .then(() => {
    cancelled = true;
    if (stop) stop();
  })
  .catch(() => {
    if (stop) stop();
  });
try {
  if (!navigator.mediaDevices?.getUserMedia)
    throw new Error("Микрофон недоступен в этой версии WebView");
  stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true },
    video: false,
  });
  if (cancelled) throw new Error("Запись отменена");
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  context = new AudioContext();
  await context.resume();
  source = context.createMediaStreamSource(stream);
  processor = context.createScriptProcessor(4096, 1, 1);
  const chunks = [];
  let count = 0;
  let voiced=0, silence=0, elapsed=0, heard=false;
  let stopped = false;
  let resolveStop;
  const finished = new Promise((resolve) => {
    resolveStop = resolve;
  });
  stop = () => {
    if (stopped) return;
    stopped = true;
    stream.getTracks().forEach((track) => track.stop());
    resolveStop();
  };
  window.addEventListener("pagehide", stop, { once: true });
  onVisibility = () => {
    if (document.hidden) stop();
  };
  document.addEventListener("visibilitychange", onVisibility);
  processor.onaudioprocess = (event) => {
    if (stopped) return;
    const available = Math.max(0, Math.floor(context.sampleRate * 30) - count);
    const chunk = event.inputBuffer.getChannelData(0).slice(0, available);
    if (chunk.length) {
      chunks.push(chunk);
      count += chunk.length;
    }
    if(automatic && chunk.length){
      const seconds=chunk.length/context.sampleRate;
      const rms=Math.sqrt(chunk.reduce((sum,x)=>sum+x*x,0)/chunk.length);
      elapsed+=seconds;
      if(rms>0.012){voiced+=seconds;silence=0;if(voiced>=0.25)heard=true;}else{silence+=seconds;}
      if((heard&&silence>=1.2)||(!heard&&elapsed>=6))stop();
    }
    if (!available || count >= context.sampleRate * 30) stop();
  };
  source.connect(processor);
  processor.connect(context.destination);
  dioxus.send({ kind: "ready" });
  timer = setTimeout(stop, 30000);
  // Команда остановки обрабатывается также во время запроса разрешения.
  await finished;
  if (automatic && !heard) throw new Error("Речь не обнаружена. Нажмите Live и попробуйте ещё раз");
  if (count < context.sampleRate * 0.15)
    throw new Error("Запись слишком короткая");
  const samples = new Float32Array(count);
  let offset = 0;
  for (const chunk of chunks) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }
  const length = Math.floor((count * 16000) / context.sampleRate);
  const wav = new ArrayBuffer(44 + length * 2);
  const view = new DataView(wav);
  const label = (offset, value) => {
    for (let i = 0; i < value.length; i++)
      view.setUint8(offset + i, value.charCodeAt(i));
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
  view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const position = (i * context.sampleRate) / 16000;
    const left = Math.floor(position);
    const fraction = position - left;
    const value = Math.max(
      -1,
      Math.min(
        1,
        samples[left] * (1 - fraction) +
          samples[Math.min(left + 1, count - 1)] * fraction,
      ),
    );
    view.setInt16(44 + i * 2, value * 32767, true);
  }
  const bytes = new Uint8Array(wav);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 32768)
    binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
  dioxus.send({ kind: "audio", data: btoa(binary) });
} catch (error) {
  dioxus.send({ kind: "error", message: String(error.message || error) });
} finally {
  clearTimeout(timer);
  if (stop) window.removeEventListener("pagehide", stop);
  if (onVisibility)
    document.removeEventListener("visibilitychange", onVisibility);
  if (stream) stream.getTracks().forEach((track) => track.stop());
  if (processor) {
    processor.onaudioprocess = null;
    processor.disconnect();
  }
  if (source) source.disconnect();
  if (context) await context.close().catch(() => {});
}
