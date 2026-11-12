const { test } = require("node:test");
const assert = require("node:assert/strict");
const { parse } = require("./model.js");
const event = (seq, extra = {}) => ({
  seq,
  ms: seq,
  kind: "step",
  name: "Событие",
  ...extra,
});

test("v3 preserves source, duration, run boundaries and causal references", () => {
  const rows = parse(
    JSON.stringify([
      event(1, { session: "a", id: "parent" }),
      event(2, {
        session: "a",
        id: "child",
        parent_id: "parent",
        file: "src/main.rs",
        line: 12,
        duration_ms: 4,
      }),
      event(1, { session: "b", id: "parent" }),
    ]),
  );
  assert.equal(rows[1].parent, rows[0].id);
  assert.notEqual(rows[0].id, rows[2].id);
  assert.equal(rows[1].duration_ms, 4);
  assert.equal(rows[1].file, "src/main.rs");
});
test("legacy appended sessions and empty lines remain readable", () => {
  const rows = parse(
    "\n" +
      [event(1), event(2), event(1), event(2)]
        .map(JSON.stringify)
        .join("\n\n") +
      "\n",
  );
  assert.equal(new Set(rows.map((row) => row.id)).size, 4);
  assert.equal(new Set(rows.map((row) => row.session)).size, 2);
});
test("out of order legacy records are not mistaken for a new run", () => {
  const rows = parse(JSON.stringify([event(2), event(1), event(3)]));
  assert.equal(new Set(rows.map((row) => row.session)).size, 1);
});
test("only incomplete last line is tolerated during live reading", () => {
  const text = JSON.stringify(event(1)) + '\n{"seq":2';
  assert.throws(() => parse(text), /строке 2/);
  assert.equal(parse(text, { partialTail: true }).length, 1);
  assert.throws(
    () => parse("{broken}\n" + JSON.stringify(event(2)), { partialTail: true }),
    /строке 1/,
  );
});
test("invalid values and duplicate IDs are rejected", () => {
  for (const raw of [event(-1), event(1, { ms: -2 }), null, []])
    assert.throws(() => parse(JSON.stringify([raw])));
  assert.throws(
    () =>
      parse(
        JSON.stringify([
          event(1, { session: "a", id: "x" }),
          event(2, { session: "a", id: "x" }),
        ]),
      ),
    /Повторный ID/,
  );
});
test("all large trace events are retained for pagination", () => {
  const rows = parse(
    JSON.stringify(
      Array.from({ length: 1600 }, (_, index) => event(index + 1)),
    ),
  );
  assert.equal(rows.length, 1600);
  assert.equal(rows.at(-1).seq, 1600);
});

test("tree branches progress horizontally with distinct leaf rows", () => {
  const rows = parse(
    JSON.stringify([
      event(1, { id: "root" }),
      event(2, { id: "a", parent_id: "root" }),
      event(3, { id: "b", parent_id: "root" }),
      event(4, { id: "leaf", parent_id: "a" }),
    ]),
  );
  const positions = require("./model.js").treeLayout(rows);
  const [root, a, b, leaf] = rows.map((row) => positions.get(row.id));
  assert.ok(root.x < a.x && a.x < leaf.x);
  assert.equal(a.x, b.x);
  assert.ok(Math.abs(a.y - b.y) >= 148);
  assert.equal(root.y, (a.y + b.y) / 2);
});
test("tree tolerates cycles, missing parents and a parent recorded later", () => {
  const rows = parse(
    JSON.stringify([
      event(1, { id: "child", parent_id: "parent" }),
      event(2, { id: "parent", parent_id: "child" }),
      event(3, { id: "missing", parent_id: "absent" }),
      event(4, { id: "self", parent_id: "self" }),
    ]),
  );
  const positions = require("./model.js").treeLayout(rows);
  assert.equal(positions.size, rows.length);
  assert.ok(positions.get(rows[0].id).x > positions.get(rows[1].id).x);
  assert.equal(
    new Set([...positions.values()].map((p) => `${p.x}/${p.y}`)).size,
    rows.length,
  );
});
test("deep legacy sequences use iterative traversal and separate sessions", () => {
  const rows = parse(
    JSON.stringify(Array.from({ length: 10000 }, (_, i) => event(i + 1))),
  );
  const positions = require("./model.js").treeLayout(rows);
  assert.equal(positions.size, rows.length);
  assert.ok(positions.get(rows.at(-1).id).x > positions.get(rows[0].id).x);
  assert.deepEqual(require("./model.js").treeLayout([]), new Map());
  assert.deepEqual(parse("", { partialTail: true }), []);
  assert.deepEqual(parse('{"seq":', { partialTail: true }), []);
  assert.throws(() => parse(""), /Нет завершённых/);
});
