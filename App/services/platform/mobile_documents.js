// WebView выполняет только выбор и чтение файла. Хранением занимается Rust.
let input;
for (let frame = 0; frame < 30; frame++) {
    input = document.getElementById("xopilot-android-materials");
    if (input) break;
    await new Promise(requestAnimationFrame);
}
if (!input) throw new Error("Не найден Android picker");

// Пропускаем desktop-перехватчик Dioxus, сохраняя обычное действие WebView.
input.addEventListener("click", event => event.stopPropagation());
input.addEventListener("change", async () => {
    input.disabled = true;
    try {
        const files = Array.from(input.files || []);
        if (files.length > 10) throw new Error("Можно выбрать до 10 файлов");
        for (const file of files) {
            if (file.size > 32 * 1024 * 1024) throw new Error("Размер файла превышает 32 МиБ");
            dioxus.send({ kind: "start", name: file.name, size: file.size });
            if (!(await dioxus.recv())) break;
            for (let offset = 0; offset < file.size; offset += 65536) {
                const part = new Uint8Array(await file.slice(offset, offset + 65536).arrayBuffer());
                let binary = "";
                for (const byte of part) binary += String.fromCharCode(byte);
                dioxus.send({ kind: "chunk", data: btoa(binary) });
                if (!(await dioxus.recv())) throw new Error("Передача файла отменена");
            }
            dioxus.send({ kind: "end" });
            if (!(await dioxus.recv())) break;
        }
    } catch (error) {
        dioxus.send({ kind: "error", message: String(error.message || error) });
    } finally {
        input.value = "";
        input.disabled = false;
        dioxus.send({ kind: "done" });
    }
});
await new Promise(() => {});
