// Описание: Постоянная упаковка Android поверх DX: имя, иконка, versionCode и подпись.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const crypto = require('node:crypto');

// Настройки CLI не содержат пароль: apksigner читает его непосредственно из защищённого файла.
function option(name, fallback) {
    const index = process.argv.indexOf(name);
    return index >= 0 ? process.argv[index + 1] : fallback;
}

// Сохраняем подпись между версиями; генерация нового ключа не является частью обычной сборки.
function main() {
    const uiTest = process.argv.includes('--ui-test');
    const preview = uiTest || process.argv.includes('--preview');
    const profile = option('--profile', 'release');
    const project = path.resolve(option('--project', `target/dx/xopilot/${profile}/android/app`));
    const output = path.resolve(option('--output', preview ? 'target/android-preview.apk' : 'dist/android.apk'));
    const sdk = process.env.ANDROID_HOME || path.resolve('target/android-toolchain/sdk');
    const versions = fs.readdirSync(path.join(sdk, 'build-tools')).sort((a, b) => a.localeCompare(b, undefined, {numeric: true}));
    const tools = path.join(sdk, 'build-tools', versions.at(-1));
    const version = fs.readFileSync('Cargo.toml', 'utf8').match(/^version\s*=\s*"([^"]+)"/m)[1];
    const parts = version.split('.').map(Number);
    const code = Number(process.env.ANDROID_VERSION_CODE || (parts[0] * 1000000 + parts[1] * 1000 + parts[2]));
    if (!Number.isSafeInteger(code) || code <= 10160 || code > 2100000000) throw Error('versionCode должен быть целым и выше прежней сборки 10160');
    const gradle = path.join(project, 'app/build.gradle.kts');
    let text = fs.readFileSync(gradle, 'utf8');
    text = text.replace(/applicationId\s*=\s*"[^"]+"/, `applicationId = "${uiTest ? 'by.xopilot.uitest' : preview ? 'by.xopilot.preview' : 'by.xopilot.app'}"`)
        .replace(/versionCode\s*=\s*\d+/, `versionCode = ${code}`)
        .replace(/versionName\s*=\s*"[^"]+"/, `versionName = "${version}"`);
    fs.writeFileSync(gradle, text);
    const res = path.join(project, 'app/src/main/res');
    for (const dir of fs.readdirSync(res).filter(name => name.startsWith('mipmap-'))) {
        fs.rmSync(path.join(res, dir, 'ic_launcher.webp'), {force: true});
    }
    fs.cpSync('App/assets/android', res, {recursive: true});
    fs.writeFileSync(path.join(res, 'values/strings.xml'), `<resources><string name="app_name">${uiTest ? 'Xopilot UI Test' : preview ? 'Xopilot Test' : 'Xopilot'}</string></resources>\n`);
    // R8 должен сохранять классы, вызываемые нативным кодом и JavascriptInterface WebView.
    fs.appendFileSync(path.join(project, 'app/proguard-rules.pro'), '\n-keep class dev.dioxus.main.** { *; }\n-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }\n');
    const variant = option('--variant', preview || profile === 'debug' ? 'debug' : 'release');
    if (!['debug', 'release'].includes(variant)) throw Error('Вариант Gradle должен быть debug или release');
    const wrapper = process.platform === 'win32' ? 'gradlew.bat' : './gradlew';
    execFileSync(wrapper, ['--no-daemon', `assemble${variant === 'release' ? 'Release' : 'Debug'}`], {cwd: project, stdio: 'inherit'});
    const folder = path.join(project, 'app/build/outputs/apk', variant);
    const unsigned = path.join(folder, variant === 'release' ? 'app-release-unsigned.apk' : 'app-debug.apk');
    fs.mkdirSync(path.dirname(output), {recursive: true});
    // Отдельный .idsig нужен только для incremental ADB; обычному APK он не требуется.
    fs.rmSync(`${output}.idsig`, {force: true});
    if (preview && variant === 'debug') {
        fs.copyFileSync(unsigned, output);
    } else {
        const keystore = path.resolve(process.env.XOPILOT_KEYSTORE || '.signing/xopilot-release.jks');
        const password = path.resolve(process.env.XOPILOT_STORE_PASSWORD_FILE || '.signing/store-password');
        // apksigner читает строки файла последовательно: один путь для двух паролей даёт EOF.
        const keyPassword = path.resolve(process.env.XOPILOT_KEY_PASSWORD_FILE || '.signing/key-password');
        const alias = process.env.XOPILOT_KEY_ALIAS || 'xopilot';
        if (!fs.existsSync(keystore) || !fs.existsSync(password) || !fs.existsSync(keyPassword)) throw Error('Для постоянной подписи нужны keystore и файлы паролей. Смотрите scripts/init_android_signing.sh');
        const aligned = path.join(path.dirname(output), 'android-aligned.apk');
        execFileSync(path.join(tools, 'zipalign'), ['-f', '-P', '16', '4', unsigned, aligned]);
        execFileSync(path.join(tools, 'apksigner'), ['sign', '--v4-signing-enabled', 'false', '--ks', keystore, '--ks-key-alias', alias,
            '--ks-pass', `file:${password}`, '--key-pass', `file:${keyPassword}`, '--out', output, aligned], {stdio: 'inherit'});
        fs.rmSync(aligned, {force: true});
    }
    execFileSync(path.join(tools, 'apksigner'), ['verify', '--print-certs', output], {stdio: 'inherit'});
    const hash = crypto.createHash('sha256');
    const fd = fs.openSync(output, 'r');
    try {
        const buffer = Buffer.alloc(1024 * 1024);
        for (;;) { const count = fs.readSync(fd, buffer); if (!count) break; hash.update(buffer.subarray(0, count)); }
    } finally { fs.closeSync(fd); }
    fs.writeFileSync(`${output}.sha256`, `${hash.digest('hex')}  ${path.basename(output)}\n`);
    console.log(`APK: ${output} · ${version} (${code})`);
}

try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
