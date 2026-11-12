// Общая модель импорта используется просмотрщиком и автоматическими тестами Node.
(function (root) {
  "use strict";
  const MAX_EVENTS = 100000;
  const MAX_BYTES = 64 * 1024 * 1024;
  function parse(text, { partialTail = false } = {}) {
    if (new TextEncoder().encode(text).byteLength > MAX_BYTES)
      throw Error("Файл больше 64 МиБ");
    let rows;
    if (text.trimStart().startsWith("[")) {
      rows = JSON.parse(text);
      if (!Array.isArray(rows)) throw Error("Ожидается массив событий");
    } else {
      const lines = text.split(/\r?\n/);
      rows = [];
      for (let index = 0; index < lines.length; index++) {
        if (!lines[index].trim()) continue;
        try {
          rows.push(JSON.parse(lines[index]));
        } catch (error) {
          if (partialTail && index === lines.length - 1 && !text.endsWith("\n"))
            break;
          throw Error(`Неверный JSON в строке ${index + 1}`);
        }
        if (rows.length > MAX_EVENTS) throw Error("Больше 100 000 событий");
      }
    }
    if (!rows.length) throw Error("Нет завершённых событий");
    if (rows.length > MAX_EVENTS) throw Error("Больше 100 000 событий");
    const seen = new Set();
    let epoch = 0;
    const legacyIds = new Set();
    return rows.map((raw, ordinal) => {
      if (!raw || typeof raw !== "object" || Array.isArray(raw))
        throw Error(`Неверное событие ${ordinal + 1}`);
      const seq = Number(raw.seq ?? ordinal + 1),
        ms = Number(raw.ms ?? 0);
      if (
        !Number.isSafeInteger(seq) ||
        seq < 0 ||
        !Number.isFinite(ms) ||
        ms < 0
      )
        throw Error(`Неверные seq/ms в событии ${ordinal + 1}`);
      const originalId = String(raw.id ?? `seq:${seq}`);
      if (!raw.session && seq === 1 && legacyIds.has(originalId)) {
        epoch++;
        legacyIds.clear();
      }
      if (!raw.session) legacyIds.add(originalId);
      const session = String(raw.session ?? `legacy-${epoch}`);
      const original = String(raw.id ?? `seq:${seq}`);
      const id = session + "/" + original;
      if (seen.has(id))
        throw Error(`Повторный ID ${original} в сессии ${session}`);
      seen.add(id);
      const parent = raw.parent_id ?? raw.parent ?? raw.flow_parent;
      const string = (value) =>
        typeof value === "string" ? value : JSON.stringify(value ?? "");
      return {
        id,
        seq,
        ms,
        ordinal,
        session,
        parent:
          parent == null || parent === ""
            ? null
            : session + "/" + String(parent),
        kind: string(raw.kind ?? "step").slice(0, 45),
        name: string(raw.name ?? "Событие").slice(0, 1000),
        detail: string(raw.detail ?? "").slice(0, 4000),
        thread: string(raw.thread ?? "?").slice(0, 120),
        file: string(raw.file ?? ""),
        line: raw.line,
        column: raw.column,
        duration_ms: raw.duration_ms,
        raw,
      };
    });
  }
  const api = { parse, MAX_EVENTS, MAX_BYTES };
  if (typeof module !== "undefined") module.exports = api;
  else root.FlowmapModel = api;
})(globalThis);
