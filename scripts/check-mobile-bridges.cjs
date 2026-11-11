// Описание: Отложенное создание DOM и повторный импорт после ошибки Android-моста.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

// Имитируем только WebView-границу: настоящий обработчик файла берём из приложения.
async function main() {
    let frames = 0;
    const listeners = new Map();
    const sent = [];
    const replies = [];
    let fail = true;
    const input = {
        dataset: {}, files: [], value: '', disabled: false,
        addEventListener: (type, callback) => listeners.set(type, callback),
    };
    const context = {
        window: {}, AbortController, Uint8Array,
        btoa: text => Buffer.from(text, 'binary').toString('base64'),
        document: {getElementById: () => frames >= 2 ? input : null},
        requestAnimationFrame: callback => setImmediate(() => { frames++; callback(); }),
        dioxus: {
            send: message => {
                sent.push(message);
                if (['start', 'chunk', 'end'].includes(message.kind)) {
                    replies.push(fail && message.kind === 'end' ? {error: 'Неизвестная модель'} : true);
                }
            },
            recv: async () => { assert(replies.length, 'Лишнее чтение ответа'); return replies.shift(); },
        },
    };
    vm.runInNewContext(`(async () => {${fs.readFileSync('App/settings/models/model_picker.js', 'utf8')} })()`, context);
    for (let attempt = 0; attempt < 20 && !listeners.has('change'); attempt++) {
        await new Promise(setImmediate);
    }
    assert.equal(input.dataset.androidPicker, 'ready', 'Поздно появившийся input не подключён');
    const blob = new Blob(['model-fixture']);
    input.files = [{name: 'test.litertlm', size: blob.size, slice: (...args) => blob.slice(...args)}];
    await listeners.get('change')();
    assert.deepEqual(sent.map(message => message.kind), ['start', 'chunk', 'end', 'done']);
    assert.equal(replies.length, 0, 'После ошибки остался ответ для следующего импорта');
    assert.equal(input.disabled, false);
    fail = false;
    sent.length = 0;
    await listeners.get('change')();
    assert.deepEqual(sent.map(message => message.kind), ['start', 'chunk', 'end', 'done']);
    assert.equal(replies.length, 0);
    assert.equal(input.disabled, false);
    console.log('✓ Android picker: поздний DOM, исходная ошибка и повторная передача');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
