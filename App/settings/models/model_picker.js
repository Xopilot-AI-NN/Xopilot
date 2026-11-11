// Android передаёт ограниченные блоки; Rust пишет их сразу на диск.
let input;
// На телефоне мост может запуститься раньше пакета DOM-изменений Dioxus.
for (let frame = 0; frame < 60; frame++) {
    input = document.getElementById('model-file-picker');
    if (input) break;
    await new Promise(requestAnimationFrame);
}
if (input) {
    window.__xopilotModelPicker?.abort();
    const controller = new AbortController();
    window.__xopilotModelPicker = controller;
    input.dataset.androidPicker = 'ready';
    input.addEventListener('click', event => event.stopPropagation(), { signal: controller.signal });
    input.addEventListener('change', async () => {
        input.disabled = true;
        try {
            const file = input.files?.[0];
            if (!file) return;
            if (file.size > 8 * 1024 ** 3) throw Error('Модель больше 8 ГиБ');
            // Каждый запрос потребляет ровно один ответ; ошибка Rust уже показана интерфейсом.
            const exchange = async message => {
                if (controller.signal.aborted) throw Error('Импорт закрыт');
                dioxus.send(message);
                const reply = await dioxus.recv();
                if (reply !== true) {
                    const error = Error(reply?.error || 'Передача отменена');
                    error.reported = Boolean(reply?.error);
                    throw error;
                }
            };
            await exchange({ kind: 'start', name: file.name, size: file.size });
            for (let offset = 0; offset < file.size; offset += 65536) {
                const bytes = new Uint8Array(await file.slice(offset, offset + 65536).arrayBuffer());
                let binary = '';
                for (const byte of bytes) binary += String.fromCharCode(byte);
                await exchange({ kind: 'chunk', data: btoa(binary) });
            }
            await exchange({ kind: 'end' });
        } catch (error) {
            if (!error.reported) dioxus.send({ kind: 'error', message: String(error.message || error) });
        } finally {
            input.value = '';
            input.disabled = false;
            dioxus.send({ kind: 'done' });
        }
    }, { signal: controller.signal });
}
await new Promise(() => {});
