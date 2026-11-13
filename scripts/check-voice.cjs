// Проверка протокола микрофона без записи реального звука пользователя.
const fs = require("node:fs");
const assert = require("node:assert/strict");
const { test } = require("node:test");
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const script = new AsyncFunction(
  "dioxus",
  "navigator",
  "window",
  "document",
  "btoa",
  fs.readFileSync("App/services/voice_record.js", "utf8"),
);

async function scenario(mode) {
  const events = [];
  let stopped = 0;
  let closed = 0;
  let processor;
  let visibilityHandler;
  const document = {
    hidden: false,
    addEventListener(name, handler) {
      visibilityHandler = handler;
    },
    removeEventListener() {},
  };
  let end;
  const command = new Promise((resolve) => {
    end = resolve;
  });
  const stream = { getTracks: () => [{ stop: () => stopped++ }] };
  const navigator = {
    mediaDevices: {
      getUserMedia: async () => {
        if (mode === "denied") throw Error("Permission denied");
        return stream;
      },
    },
  };
  class AudioContext {
    sampleRate = 16000;
    async resume() {}
    async close() {
      closed++;
    }
    createMediaStreamSource() {
      return { connect() {}, disconnect() {} };
    }
    createScriptProcessor() {
      processor = { connect() {}, disconnect() {}, onaudioprocess: null };
      return processor;
    }
  }
  const window = {
    AudioContext,
    addEventListener() {},
    removeEventListener() {},
  };
  const bridge = {
    recv: () => command,
    send(event) {
      events.push(event);
      if (event.kind === "ready")
        queueMicrotask(() => {
          processor.onaudioprocess({
            inputBuffer: {
              getChannelData: () => new Float32Array(8000).fill(0.5),
            },
          });
          if (mode === "background") {
            document.hidden = true;
            visibilityHandler();
          } else end("stop");
        });
    },
  };
  if (mode === "cancel") end("stop");
  await script(bridge, navigator, window, document, (binary) =>
    Buffer.from(binary, "binary").toString("base64"),
  );
  return { events, stopped, closed };
}

test("recording produces bounded WAV and releases audio resources", async () => {
  const result = await scenario("record");
  const event = result.events.find((event) => event.kind === "audio");
  assert.ok(event);
  const bytes = Buffer.from(event.data, "base64");
  assert.equal(bytes.toString("ascii", 0, 4), "RIFF");
  assert.equal(bytes.readUInt32LE(24), 16000);
  assert.equal(bytes.length, 16044);
  assert.equal(result.closed, 1);
  assert.ok(result.stopped > 0);
});
test("denied permission returns an error without recording", async () => {
  const result = await scenario("denied");
  assert.equal(result.events[0].kind, "error");
  assert.equal(result.closed, 0);
});
test("cancelling permission request stops a subsequently granted stream", async () => {
  const result = await scenario("cancel");
  assert.equal(result.events[0].kind, "error");
  assert.equal(result.stopped, 1);
  assert.equal(result.closed, 0);
});

test("moving to background stops capture and releases resources", async () => {
  const result = await scenario("background");
  assert.ok(result.events.some((event) => event.kind === "audio"));
  assert.equal(result.closed, 1);
  assert.ok(result.stopped > 0);
});
