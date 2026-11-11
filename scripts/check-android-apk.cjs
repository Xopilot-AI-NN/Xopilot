// Описание: Проверяем реальные ELF и ZIP-выравнивание готового APK до установки на телефон.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const assert = require('node:assert/strict');

// Проверяем p_align и взаимное расположение смещений каждого LOAD-сегмента.
function checkElf(file, name) {
    const text = execFileSync('readelf', ['-lW', file], {encoding: 'utf8'});
    const loads = text.split('\n').map(line => line.trim().split(/\s+/)).filter(row => row[0] === 'LOAD');
    assert(loads.length, `${name}: LOAD-сегменты отсутствуют`);
    for (const row of loads) {
        const alignment = BigInt(row.at(-1));
        assert(alignment >= 16384n && (alignment & (alignment - 1n)) === 0n, `${name}: LOAD не выровнен на 16 КиБ`);
        assert.equal(BigInt(row[1]) % 16384n, BigInt(row[2]) % 16384n, `${name}: смещение LOAD несовместимо с 16 КиБ`);
    }
    console.log(`✓ ${name}: ELF 16 КиБ`);
}

// Распаковываем только в собственный временный файл, не используя пути из архива.
function main() {
    const apk = path.resolve(process.argv[2] || 'target/dx/xopilot/debug/android/app/app/build/outputs/apk/debug/app-debug.apk');
    const sdk = process.env.ANDROID_HOME || path.resolve('target/android-toolchain/sdk');
    const tools = fs.readdirSync(path.join(sdk, 'build-tools')).sort((a, b) => a.localeCompare(b, undefined, {numeric: true})).at(-1);
    const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'xopilot-apk-check-'));
    try {
        const entries = execFileSync('unzip', ['-Z1', apk], {encoding: 'utf8'})
            .trim().split('\n').filter(name => /^lib\/(arm64-v8a|x86_64)\/[^/]+\.so$/.test(name));
        assert(entries.length, 'В APK отсутствуют 64-битные библиотеки');
        for (const [index, name] of entries.entries()) {
            const file = path.join(temporary, `${index}.so`);
            const fd = fs.openSync(file, 'w');
            try {
                execFileSync('unzip', ['-p', apk, name], {stdio: ['ignore', fd, 'pipe']});
            } finally {
                fs.closeSync(fd);
            }
            checkElf(file, name);
        }
        execFileSync(path.join(sdk, 'build-tools', tools, 'zipalign'), ['-c', '-P', '16', '4', apk]);
        console.log('✓ APK: ZIP-выравнивание 16 КиБ');
    } finally {
        fs.rmSync(temporary, {recursive: true, force: true});
    }
}

try {
    main();
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
