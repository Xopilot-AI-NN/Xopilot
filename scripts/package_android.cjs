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
    const devTest = process.argv.includes('--dev-test');
    const profile = option('--profile', devTest ? 'debug' : 'release');
    if (profile !== (devTest ? 'debug' : 'release') || ['--ui-test', '--preview', '--variant'].some(flag => process.argv.includes(flag))) {
        throw Error('Собирайте через scripts/build_android.sh [--dev-test]');
    }
    const project = path.resolve(option('--project', `target/dx/xopilot/${profile}/android/app`));
    const output = path.resolve(option('--output', devTest ? 'target/xopilot-dev-test.apk' : 'dist/android.apk'));
    const sdk = process.env.ANDROID_HOME || path.resolve('target/android-toolchain/sdk');
    const versions = fs.readdirSync(path.join(sdk, 'build-tools')).sort((a, b) => a.localeCompare(b, undefined, {numeric: true}));
    const tools = path.join(sdk, 'build-tools', versions.at(-1));
    const version = fs.readFileSync('Cargo.toml', 'utf8').match(/^version\s*=\s*"([^"]+)"/m)[1];
    const parts = version.split('.').map(Number);
    const code = Number(process.env.ANDROID_VERSION_CODE || (parts[0] * 1000000 + parts[1] * 1000 + parts[2]));
    if (!Number.isSafeInteger(code) || code <= 10160 || code > 2100000000) throw Error('versionCode должен быть целым и выше прежней сборки 10160');
    const gradle = path.join(project, 'app/build.gradle.kts');
    let text = fs.readFileSync(gradle, 'utf8');
    text = text.replace(/applicationId\s*=\s*"[^"]+"/, 'applicationId = "by.xopilot.app"')
        .replace(/versionCode\s*=\s*\d+/, `versionCode = ${code}`)
        .replace(/versionName\s*=\s*"[^"]+"/, `versionName = "${version}"`);
    fs.writeFileSync(gradle, text);
    const res = path.join(project, 'app/src/main/res');
    for (const dir of fs.readdirSync(res).filter(name => name.startsWith('mipmap-'))) {
        fs.rmSync(path.join(res, dir, 'ic_launcher.webp'), {force: true});
    }
    fs.cpSync('App/assets/android', res, {recursive: true});
    fs.writeFileSync(path.join(res, 'values/strings.xml'), '<resources><string name="app_name">Xopilot</string></resources>\n');
    // R8 должен сохранять классы, вызываемые нативным кодом и JavascriptInterface WebView.
    fs.appendFileSync(path.join(project, 'app/proguard-rules.pro'), '\n-keep class dev.dioxus.main.** { *; }\n-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }\n');
    const manifestPath = path.join(project, 'app/src/main/AndroidManifest.xml');
    const marker = '<meta-data android:name="by.xopilot.DEV_TEST" android:value="true" />';
    let manifest = fs.readFileSync(manifestPath, 'utf8').replace(`    ${marker}\n`, '');
    if (devTest) manifest = manifest.replace('</application>', `    ${marker}\n</application>`);
    fs.writeFileSync(manifestPath, manifest);
    const wrapper = process.platform === 'win32' ? 'gradlew.bat' : './gradlew';
    const keystore = path.resolve(process.env.XOPILOT_KEYSTORE || '.signing/xopilot-release.jks');
    const password = path.resolve(process.env.XOPILOT_STORE_PASSWORD_FILE || '.signing/store-password');
    const keyPassword = path.resolve(process.env.XOPILOT_KEY_PASSWORD_FILE || '.signing/key-password');
    const alias = process.env.XOPILOT_KEY_ALIAS || 'xopilot';
    if (![keystore, password, keyPassword].every(file => fs.existsSync(file))) {
        throw Error('Для обеих сборок нужны существующий ключ релиза Xopilot и файлы его паролей');
    }
    // Debug-профиль Rust нужен WebView для тестов. Сам APK всегда собирается как release Gradle.
    execFileSync(wrapper, ['--no-daemon', 'assembleRelease'], {cwd: project, stdio: 'inherit'});
    const unsigned = path.join(project, 'app/build/outputs/apk/release/app-release-unsigned.apk');
    fs.mkdirSync(path.dirname(output), {recursive: true});
    const work = fs.mkdtempSync(path.join(path.dirname(output), '.android-sign-'));
    try {
        const aligned = path.join(work, 'aligned.apk');
        const signed = path.join(work, 'signed.apk');
        execFileSync(path.join(tools, 'zipalign'), ['-f', '-P', '16', '4', unsigned, aligned]);
        execFileSync(path.join(tools, 'apksigner'), ['sign', '--v4-signing-enabled', 'false', '--ks', keystore, '--ks-key-alias', alias,
            '--ks-pass', `file:${password}`, '--key-pass', `file:${keyPassword}`, '--out', signed, aligned], {stdio: 'inherit'});
        const report = execFileSync(path.join(tools, 'apksigner'), ['verify', '--print-certs', signed], {encoding: 'utf8'});
        const fingerprint = fs.readFileSync('App/android/signing-certificate.sha256', 'utf8').trim();
        if (!report.includes(`certificate SHA-256 digest: ${fingerprint}`)) {
            throw Error('Подпись не совпадает с постоянным сертификатом Xopilot');
        }
        fs.rmSync(`${output}.idsig`, {force: true});
        fs.renameSync(signed, output);
        console.log(report.trim());
    } finally {
        fs.rmSync(work, {recursive: true, force: true});
    }
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
