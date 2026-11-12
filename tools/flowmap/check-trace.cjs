// Изолированные процессы проверяют настоящий журнал, включая disabled/values режимы.
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = fs.mkdtempSync(path.resolve("target/flowmap-check-"));
const binary = path.resolve(
  "target/debug/examples/flowmap_nodes_demo" +
    (process.platform === "win32" ? ".exe" : ""),
);
const trace = path.join(root, "trace.jsonl");
const run = (extra) =>
  execFileSync(binary, [], {
    env: {
      ...process.env,
      XOPILOT_FLOW_PATH: trace,
      XOPILOT_FLOW_TRACE: "1",
      XOPILOT_FLOW_VALUES: "0",
      ...extra,
    },
    stdio: "pipe",
  });
run({ XOPILOT_FLOW_TRACE: "0" });
assert(!fs.existsSync(trace), "Выключенная трассировка создаёт файл");
run({ FLOWMAP_STRESS: "1", FLOWMAP_TEST_ERROR: "1" });
const first = fs.readFileSync(trace, "utf8").trim().split("\n").map(JSON.parse);
assert(first.length > 400);
const ids = new Map(first.map((event) => [event.id, event]));
assert.equal(ids.size, first.length);
first.forEach((event, index) => {
  assert.equal(
    event.seq,
    index + 1,
    "Порядок seq расходится с порядком записи",
  );
  if (event.parent_id) assert(ids.has(event.parent_id), "Неизвестный родитель");
});
assert(
  first.some(
    (event) => event.file.includes("flowmap_nodes_demo.rs") && event.line > 0,
  ),
);
assert(
  first.some(
    (event) => event.kind === "variable" && event.detail.includes("скрыто"),
  ),
);
assert(first.some((event) => event.kind === "error"));
assert(
  first.some((event) => event.kind === "end" && event.detail === "cancelled"),
);
for (const event of first.filter((event) => event.name === "После await")) {
  assert(
    ids.get(event.parent_id).name.startsWith("Async "),
    "Потерян контекст после await",
  );
}
for (const event of first.filter((event) => event.kind === "end"))
  assert(event.duration_ms >= 0);
run({ XOPILOT_FLOW_VALUES: "1" });
const all = fs.readFileSync(trace, "utf8").trim().split("\n").map(JSON.parse);
assert.equal(
  new Set(all.map((event) => event.id)).size,
  all.length,
  "Повторные ID при дописывании",
);
assert(
  all
    .slice(first.length)
    .some((event) => event.kind === "variable" && event.detail === "21"),
);
const limited = path.join(root, "limited.jsonl");
run({ XOPILOT_FLOW_PATH: limited, XOPILOT_FLOW_MAX_EVENTS: "3" });
assert.equal(fs.readFileSync(limited, "utf8").trim().split("\n").length, 3);
const broken = path.join(root, "broken.jsonl");
fs.writeFileSync(broken, '{"seq":');
run({ XOPILOT_FLOW_PATH: broken });
assert.equal(
  fs.readFileSync(broken, "utf8"),
  '{"seq":',
  "Повреждённый хвост был перезаписан",
);
const { parse } = require("./model.js");
assert.equal(parse(fs.readFileSync(trace, "utf8")).length, all.length);
console.log(
  "✓ Потоки, async/await, отмена, IO, seq, сессии, лимит, исходники и скрытие значений",
);
console.log("Артефакты: " + root);
