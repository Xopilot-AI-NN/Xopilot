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
