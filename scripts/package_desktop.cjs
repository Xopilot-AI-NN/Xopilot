// Описание: Прежние desktop-артефакты выпускаются из Rust: ZIP и отдельный исполняемый файл.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

// Шрифты, логотип и LiteRT встроены в бинарь; пользовательские модели в релиз не попадают.
function main() {
    const platform = process.argv[2] || (process.platform === 'win32' ? 'windows' : 'linux');
    if (!['linux', 'windows'].includes(platform)) throw Error('Ожидалась платформа linux или windows');
    const version = fs.readFileSync('Cargo.toml', 'utf8').match(/^version\s*=\s*"([^"]+)"/m)[1];
    const buildType = process.env.GITHUB_REF_NAME?.startsWith('v') ? 'Release' : 'Dev';
    const system = platform === 'windows' ? 'Windows' : 'Linux';
    const archiveName = `Xopilot-${buildType}-${version.replaceAll('.', '_')}-${system}.zip`;
    const folder = path.resolve(`target/dx/xopilot/release/${platform}/app`);
    const source = path.join(folder, platform === 'windows' ? 'xopilot.exe' : 'xopilot');
    const binary = platform === 'windows' ? 'Xopilot.exe' : 'Xopilot';
    const temporary = path.resolve(`target/package-${platform}`);
    fs.rmSync(temporary, {recursive: true, force: true});
    fs.mkdirSync(temporary, {recursive: true});
    fs.mkdirSync('dist', {recursive: true});
    fs.copyFileSync(source, path.join(temporary, binary));
    fs.copyFileSync(source, path.join('dist', binary));
    fs.copyFileSync('LICENSE', path.join(temporary, 'LICENSE'));
    fs.copyFileSync('App/native/runtime-licenses.zip', path.join(temporary, 'runtime-licenses.zip'));
    fs.writeFileSync(path.join(temporary, 'README.txt'), platform === 'linux'
        ? 'Xopilot — Rust / Dioxus\nЗапуск: ./Xopilot\nНужны системные GTK3, WebKitGTK 4.1 и libxdo. Модели скачиваются из приложения.\n'
        : 'Xopilot — Rust / Dioxus\nЗапуск: Xopilot.exe\nИспользуется Microsoft Edge WebView2 Runtime. Модели скачиваются из приложения.\n');
    if (platform === 'windows') {
        // DLL системного VC runtime, если их добавил bundler, остаются рядом с .exe в ZIP.
        for (const name of fs.readdirSync(folder).filter(name => name.toLowerCase().endsWith('.dll'))) {
            fs.copyFileSync(path.join(folder, name), path.join(temporary, name));
        }
        const destination = path.resolve('dist', archiveName);
        const quote = value => value.replaceAll("'", "''");
        execFileSync('pwsh', ['-NoProfile', '-Command', `Compress-Archive -Path '${quote(temporary)}/*' -DestinationPath '${quote(destination)}' -Force`], {stdio: 'inherit'});
    } else {
        fs.chmodSync(path.join(temporary, binary), 0o755);
        fs.chmodSync(path.join('dist', binary), 0o755);
        fs.rmSync(path.join('dist', archiveName), {force: true});
        execFileSync('zip', ['-qr', path.resolve('dist', archiveName), '.'], {cwd: temporary});
    }
    console.log(`Готово: dist/${archiveName} и dist/${binary}`);
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
