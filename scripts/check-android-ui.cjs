// Описание: Реальные события DOM в тестовом APK через ADB и штатный WebView DevTools.
// Допускается только by.xopilot.test: личный APK и его SQLCipher не очищаются.
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const app = "by.xopilot.test";
const adbPath =
  process.env.ADB ||
  (process.env.ANDROID_HOME
    ? path.join(process.env.ANDROID_HOME, "platform-tools/adb")
    : "target/android-toolchain/sdk/platform-tools/adb");
const root = path.resolve(
  "target/android-ui-" + new Date().toISOString().replaceAll(/[:.]/g, "-"),
);
const results = [];
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let port,
  ws,
  sequence = 0;
const pending = new Map();
// Один явно выбранный телефон; при нескольких устройствах нужен ANDROID_SERIAL.
function adb(...args) {
  return execFileSync(adbPath, args, { encoding: "utf8", timeout: 30000 });
}
async function connect() {
  // am start возвращается раньше появления PID при холодном запуске после pm clear.
  let pid;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { pid = adb("shell", "pidof", app).trim().split(" ")[0]; } catch (_) {}
    if (pid) break;
    await wait(100);
  }
  if (!pid) throw Error("Тестовый процесс не запущен");
  if (port) adb("forward", "--remove", `tcp:${port}`);
  port = Number(
    adb(
      "forward",
      "tcp:0",
      `localabstract:webview_devtools_remote_${pid}`,
    ).trim(),
  );
  let target;
  for (let i = 0; i < 100; i++) {
    try {
      const targets = await (
        await fetch(`http://127.0.0.1:${port}/json/list`)
      ).json();
      target = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (target) break;
    } catch (_) {}
    await wait(100);
  }
  if (!target)
    throw Error(
      "WebView DevTools недоступны. Нужен debug APK, собранный с --ui-test.",
    );
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data),
      call = pending.get(message.id);
    if (!call) return;
    pending.delete(message.id);
    clearTimeout(call.timer);
    if (message.error || message.result?.exceptionDetails)
      call.reject(
        Error(JSON.stringify(message.error || message.result.exceptionDetails)),
      );
    else call.resolve(message.result?.result?.value);
  });
}
// Таймаут нужен и при свёрнутой Activity: JS может приостанавливаться системой.
function evaluate(script) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error("WebView не ответил за 15 секунд"));
    }, 15000);
    pending.set(id, { resolve, reject, timer });
    ws.send(
      JSON.stringify({
        id,
        method: "Runtime.evaluate",
        params: {
          expression: `(async()=>{${script}})()`,
          awaitPromise: true,
          returnByValue: true,
          userGesture: true,
        },
      }),
    );
  });
}
function launch() {
  return adb(
    "shell",
    "am",
    "start",
    "-a",
    "android.intent.action.MAIN",
    "-c",
    "android.intent.category.LAUNCHER",
    "-n",
    app + "/dev.dioxus.main.MainActivity",
    "-f",
    "0x10200000",
    "-W",
  );
}
function screenshot(name) {
  fs.writeFileSync(
    path.join(root, name + ".png"),
    execFileSync(adbPath, ["exec-out", "screencap", "-p"], { timeout: 10000 }),
  );
}
(async () => {
  fs.mkdirSync(root, { recursive: true, mode: 0o700 });
  const devices = adb("devices")
    .trim()
    .split("\n")
    .slice(1)
    .filter((s) => /\sdevice$/.test(s));
  if (!devices.length)
    throw Error(
      "Подключите телефон и подтвердите USB-отладку. Личные приложения не изменены.",
    );
  if (devices.length > 1 && !process.env.ANDROID_SERIAL)
    throw Error("Выберите телефон через ANDROID_SERIAL");
  const apk = path.resolve(process.argv[2] || "target/android-ui-test.apk");
  if (!fs.existsSync(apk))
    throw Error("Сначала соберите тестовый APK: ./scripts/test.sh apk");
  // Идентификатор читается из APK до установки, чтобы переданный production APK не затронул данные.
  const sdk = process.env.ANDROID_HOME || "target/android-toolchain/sdk";
  const versions = fs
    .readdirSync(path.join(sdk, "build-tools"))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const aapt = path.join(sdk, "build-tools", versions.at(-1), "aapt");
  const badging = execFileSync(aapt, ["dump", "badging", apk], {
    encoding: "utf8",
  });
  if (!badging.includes("package: name='" + app + "'"))
    throw Error("Отказ: допускается только изолированный by.xopilot.test");
  adb("install", "--no-incremental", "-r", apk);
  adb("shell", "am", "force-stop", app);
  adb("shell", "pm", "clear", app);
  launch();
  await connect();
  const ui = require("./ui/client.cjs")(evaluate, results);
  await require("./ui/offline.cjs")(ui);
  if(process.env.XOPILOT_TEST_SPEECH === "1"){
    await ui.click("Открыть меню");await ui.click("Настройки");await ui.click("Персонализация");
    await ui.click("Проверить голос");
    await ui.until("return !!document.querySelector('.speech-progress') || !!document.querySelector('.snackbar.error');","Системный TTS не запустился",10000);
    await ui.until("return !document.querySelector('.speech-progress');","Системный TTS не завершился",20000);
    await ui.check("Локальный Android TTS завершил тестовую фразу","return !document.querySelector('.snackbar.error');");
    await ui.close();
  }
  screenshot("offline");
  const pid = adb("shell", "pidof", app).trim();
  await ui.input("#chat-prompt", "Черновик перед уходом в фон");
  await ui.wait(400);
  adb("shell", "input", "keyevent", "KEYCODE_HOME");
  await wait(300);
  launch();
  await ui.check(
    "Возврат из фона сохраняет черновик",
    "return document.querySelector('#chat-prompt').value==='Черновик перед уходом в фон';",
  );
  if (adb("shell", "pidof", app).trim() !== pid)
    throw Error("Home пересоздал процесс");
  results.push("Home сохраняет тот же процесс");
  await ui.click("Открыть меню");
  await ui.click("Настройки");
  adb("shell", "input", "keyevent", "KEYCODE_BACK");
  await wait(300);
  await ui.check(
    "Android Back закрывает окно",
    "return !document.querySelector('.dialog');",
  );
  adb("shell", "input", "keyevent", "KEYCODE_HOME");
  await wait(500);
  adb("shell", "am", "kill", app);
  ws.close();
  await wait(500);
  launch();
  await connect();
  await ui.until(
    "return document.querySelector('.app')?.dataset.ready==='true';",
    "Нет истории после уничтожения процесса",
    20000,
  );
  await ui.check(
    "Черновик пережил уничтожение процесса",
    "return document.querySelector('#chat-prompt').value==='Черновик перед уходом в фон';",
  );
  // Настоящее касание открывает IME; проверяем геометрию после изменения visualViewport.
  const r = await evaluate(
    "const r=document.querySelector('#chat-prompt').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,dpr:devicePixelRatio,height:visualViewport.height};",
  );
  adb(
    "shell",
    "input",
    "tap",
    String(Math.round(r.x * r.dpr)),
    String(Math.round(r.y * r.dpr)),
  );
  await wait(1200);
  await ui.check(
    "Системная клавиатура действительно открылась",
    `return visualViewport.height<${r.height}-50;`,
  );
  await ui.check(
    "Строка ввода находится в доступной области",
    "return document.querySelector('.composer').getBoundingClientRect().bottom<=visualViewport.height+1;",
  );
  screenshot("keyboard");
  adb("shell", "input", "keyevent", "KEYCODE_BACK");
  fs.writeFileSync(
    path.join(root, "result.json"),
    JSON.stringify(
      {
        platform: "Android WebView via ADB",
        package: app,
        checks: results,
        device: adb("shell", "getprop", "ro.product.model").trim(),
        pageSize: adb("shell", "getconf", "PAGE_SIZE").trim(),
      },
      null,
      2,
    ),
  );
  console.log(`${results.length} проверок пройдено. Артефакты: ${root}`);
})()
  .catch((error) => {
    console.error(error.message);
    if (fs.existsSync(root))
      fs.writeFileSync(path.join(root, "failure.txt"), String(error.stack));
    process.exitCode = 1;
  })
  .finally(() => {
    if (ws) ws.close();
    for (const call of pending.values()) {
      clearTimeout(call.timer);
      call.reject(Error("Стенд закрыт"));
    }
    pending.clear();
    if (port)
      try {
        adb("forward", "--remove", `tcp:${port}`);
      } catch (_) {}
  });
