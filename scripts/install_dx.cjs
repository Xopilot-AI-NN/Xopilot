// Описание: CI получает закреплённый официальный Dioxus CLI и сверяет SHA-256 вместо долгой пересборки инструмента.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {Readable} = require('node:stream');
const {pipeline} = require('node:stream/promises');

// Проверяем HTTP-ошибку до записи: HTML страницы ошибки не должен становиться исполняемым файлом.
async function fetchFile(url, target) {
    const response = await fetch(url);
    if (!response.ok) throw Error(`Dioxus CLI: HTTP ${response.status}`);
    await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(target));
}

// Официальные архивы могут иметь корневую папку; выбираем только файл с ожидаемым именем.
function findBinary(root, name) {
    for (const entry of fs.readdirSync(root, {withFileTypes: true})) {
        const candidate = path.join(root, entry.name);
        if (entry.isFile() && entry.name === name) return candidate;
        if (entry.isDirectory()) { const found = findBinary(candidate, name); if (found) return found; }
    }
}

// Версия совпадает с Cargo.lock. URL и проверяемый checksum берутся из одного официального релиза.
async function main() {
    const version = '0.7.10';
    const windows = process.platform === 'win32';
    if (process.arch !== 'x64' || (!windows && process.platform !== 'linux')) throw Error('Этот установщик CI предназначен для x64 Linux/Windows');
    const stem = `dx-x86_64-${windows ? 'pc-windows-msvc' : 'unknown-linux-gnu'}`;
    const archiveName = `${stem}.${windows ? 'zip' : 'tar.gz'}`;
    const base = `https://github.com/DioxusLabs/dioxus/releases/download/v${version}`;
    const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'xopilot-dx-'));
    try {
        const archive = path.join(temporary, archiveName);
        const checksum = path.join(temporary, 'sha256');
        await Promise.all([fetchFile(`${base}/${archiveName}`, archive), fetchFile(`${base}/${stem}.sha256`, checksum)]);
        const lines = fs.readFileSync(checksum, 'utf8').trim().split('\n');
        const expected = lines.find(line => line.includes(archiveName))?.match(/[0-9a-f]{64}/i)?.[0];
        if (!expected) throw Error('В официальном checksum отсутствует нужный архив DX');
        const hash = crypto.createHash('sha256');
        for await (const chunk of fs.createReadStream(archive)) hash.update(chunk);
        if (hash.digest('hex') !== expected.toLowerCase()) throw Error('SHA-256 Dioxus CLI не совпадает');
        const unpacked = path.join(temporary, 'unpacked');
        fs.mkdirSync(unpacked);
        if (windows) {
            const quote = value => value.replaceAll("'", "''");
            execFileSync('pwsh', ['-NoProfile', '-Command', `Expand-Archive -LiteralPath '${quote(archive)}' -DestinationPath '${quote(unpacked)}'`]);
        } else execFileSync('tar', ['-xzf', archive, '-C', unpacked]);
        const name = windows ? 'dx.exe' : 'dx';
        const binary = findBinary(unpacked, name);
        if (!binary) throw Error('В архиве отсутствует dx');
        const folder = path.join(process.env.RUNNER_TEMP || os.tmpdir(), 'xopilot-tools');
        fs.mkdirSync(folder, {recursive: true});
        fs.copyFileSync(binary, path.join(folder, name));
        if (!windows) fs.chmodSync(path.join(folder, name), 0o755);
        execFileSync(path.join(folder, name), ['--version'], {stdio: 'inherit'});
        if (process.env.GITHUB_PATH) fs.appendFileSync(process.env.GITHUB_PATH, `${folder}\n`);
        console.log(`Dioxus CLI: ${folder}`);
    } finally { fs.rmSync(temporary, {recursive: true, force: true}); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
