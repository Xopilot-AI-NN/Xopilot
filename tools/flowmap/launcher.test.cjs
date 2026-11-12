// Проверяем настоящую CLI-команду с Rust-демонстрацией и HTTP-просмотрщиком.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("node:path");
const { setTimeout: delay } = require("node:timers/promises");
const { parse } = require("./model.js");

test(
  "one command connects a real trace and cleans up its server",
  { timeout: 120000 },
  async () => {
    const child = spawn(
      process.execPath,
      ["scripts/fmap", "--demo", "--no-browser"],
      {
        cwd: path.resolve(__dirname, "../.."),
        env: { ...process.env, FLOWMAP_PORT: "0" },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk;
    });
    child.stderr.on("data", (chunk) => {
      output += chunk;
    });
    const exited = new Promise((resolve, reject) => {
      child.once("exit", (code, signal) => resolve({ code, signal }));
      child.once("error", reject);
    });
    try {
      let url;
      for (let attempt = 0; attempt < 900; attempt++) {
        assert.equal(child.exitCode, null, output);
        url = output.match(/http:\/\/127\.0\.0\.1:\d+\/\?live=1/)?.[0];
        if (url && output.includes("Приложение завершено.")) break;
        await delay(100);
      }
      assert.ok(url, output);
      assert.match(output, /Приложение завершено\./);
      const status = await (
        await fetch(new URL("/flowmap-status", url))
      ).json();
      assert.match(status.trace, /^xopilot-\d+-\d+\.jsonl$/);
      const rows = parse(
        await (await fetch(new URL("/flowmap-trace", url))).text(),
      );
      assert.ok(rows.length > 20);
      assert.ok(rows.some((row) => row.parent));
      const page = await (await fetch(url)).text();
      assert.match(page, /model.js/);
      child.kill("SIGTERM");
      const result = await exited;
      assert.equal(result.code, 143);
      await assert.rejects(fetch(url));
    } finally {
      if (child.exitCode === null && child.signalCode === null) {
        child.kill("SIGTERM");
        await exited;
      }
    }
  },
);

// Каталог ограничивает выбор своей папкой. Новые файлы и дописанные события
// доступны без перезапуска, произвольный путь через HTTP открыть нельзя.
test(
  "catalogue selects traces and reflects new files and live writes",
  { timeout: 10000 },
  async () => {
    const fs = require("node:fs/promises");
    const os = require("node:os");
    const directory = await fs.mkdtemp(
      path.join(os.tmpdir(), "flowmap-catalogue-"),
    );
    const row = (seq) =>
      JSON.stringify({ seq, ms: seq, name: `event-${seq}` }) + "\n";
    await fs.writeFile(path.join(directory, "first.jsonl"), row(1));
    await fs.writeFile(path.join(directory, "ignored.txt"), "private");
    await fs.symlink(
      path.join(directory, "ignored.txt"),
      path.join(directory, "link.jsonl"),
    );
    const server = spawn(process.execPath, ["tools/flowmap/serve.cjs"], {
      cwd: path.resolve(__dirname, "../.."),
      env: { ...process.env, FLOWMAP_PORT: "0", FLOWMAP_TRACE_DIR: directory },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    server.stdout.on("data", (chunk) => {
      output += chunk;
    });
    const exited = new Promise((resolve) => server.once("exit", resolve));
    try {
      let url;
      for (let attempt = 0; attempt < 100; attempt++) {
        url = output.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0];
        if (url) break;
        await delay(20);
      }
      assert.ok(url, output);
      const catalogue = async () =>
        (await fetch(url + "/flowmap-files")).json();
      const first = await catalogue();
      assert.deepEqual(
        first.files.map((file) => file.name),
        ["first.jsonl"],
      );
      assert.equal(first.selected, first.files[0].id);
      assert.equal(first.files[0].location, undefined);
      const endpoint =
        url + "/flowmap-trace?file=" + encodeURIComponent(first.selected);
      const snapshot = await fetch(endpoint);
      assert.equal(parse(await snapshot.text()).length, 1);
      await fs.appendFile(path.join(directory, "first.jsonl"), row(2));
      const updated = await fetch(endpoint);
      assert.notEqual(
        updated.headers.get("X-Flowmap-Revision"),
        snapshot.headers.get("X-Flowmap-Revision"),
      );
      assert.equal(parse(await updated.text()).length, 2);
      await fs.writeFile(path.join(directory, "second.jsonl"), row(3));
      assert.equal((await catalogue()).files.length, 2);
      assert.equal(
        (await fetch(url + "/flowmap-trace?file=../ignored.txt")).status,
        404,
      );
      await fs.unlink(path.join(directory, "first.jsonl"));
      await fs.symlink(
        path.join(directory, "ignored.txt"),
        path.join(directory, "first.jsonl"),
      );
      assert.equal((await fetch(endpoint)).status, 404);
    } finally {
      server.kill("SIGTERM");
      await exited;
      await fs.rm(directory, { recursive: true, force: true });
    }
  },
);
