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
