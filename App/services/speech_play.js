// Системная речь WebView2. Выбираю только локальный голос и освобождаю очередь при остановке.
let cancelled = false;
let synthesis;
let rejectActive;
const stop = () => { cancelled = true; synthesis?.cancel(); rejectActive?.(new Error("Озвучивание остановлено")); };
dioxus.recv().then(stop).catch(stop);
const onVisibility = () => { if (document.hidden) stop(); };
document.addEventListener('visibilitychange', onVisibility);
try {
  synthesis = window.speechSynthesis;
  if (!synthesis) throw new Error('Системное озвучивание недоступно');
  let voices = synthesis.getVoices();
  if (!voices.length) {
    await new Promise(resolve => {
      const changed = () => { clearTimeout(timer); synthesis.removeEventListener('voiceschanged', changed); resolve(); };
      const timer = setTimeout(changed, 2000);
      synthesis.addEventListener('voiceschanged', changed);
    });
    voices = synthesis.getVoices();
  }
  const voice = voices.find(v => v.localService && v.lang.startsWith('ru'));
  if (!voice) throw new Error('Локальный русский голос не найден');
  for (const text of __XOPILOT_TEXT__) {
    if (cancelled) throw new Error('Озвучивание остановлено');
    await new Promise((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = 'ru-RU';
      rejectActive = reject;
      utterance.onend = () => { rejectActive=undefined; resolve(); };
      utterance.onerror = () => { rejectActive=undefined; reject(new Error('Ошибка голоса')); };
      synthesis.speak(utterance);
    });
  }
  dioxus.send({ok: true});
} catch (error) {
  dioxus.send({error: String(error.message || error)});
} finally {
  document.removeEventListener('visibilitychange', onVisibility);
  synthesis?.cancel();
}
