// Создано ChatGPT: Flow Map v2, граф отмеченных событий, без серверов и внешних библиотек.
"use strict";
(() => {
  const svgNS = "http://www.w3.org/2000/svg";
  const $ = (s) => document.querySelector(s);
  const svg = $("#graph"),
    shell = $("#canvas-shell"),
    viewport = $("#viewport");
  const edgesLayer = $("#edges"),
    nodesLayer = $("#nodes");
  const details = $("#details"),
    toastBox = $("#toast");
  const KIND = {
    start: { icon: "▶", label: "Запуск", stroke: "#49b992", bg: "#1b3835" },
    end: { icon: "✓", label: "Завершение", stroke: "#57c9a3", bg: "#20392e" },
    call: { icon: "ƒ", label: "Вызов", stroke: "#ab93ed", bg: "#302a43" },
    step: { icon: "↳", label: "Шаг", stroke: "#7daee2", bg: "#253546" },
    branch: { icon: "◇", label: "Условие", stroke: "#efb95e", bg: "#463a25" },
    variable: {
      icon: "x",
      label: "Переменная",
      stroke: "#66c5d6",
      bg: "#1f3c45",
    },
    file_read: { icon: "⇠", label: "Чтение", stroke: "#759fe4", bg: "#263a5a" },
    file_write: {
      icon: "⇢",
      label: "Запись",
      stroke: "#dc9580",
      bg: "#4b332e",
    },
    error: { icon: "!", label: "Ошибка", stroke: "#f18082", bg: "#4b292f" },
  };
  const NODE_W = 262,
    NODE_H = 98,
    MAX_VISIBLE = 500,
    MAX_LINES = 100000,
    MAX_BYTES = 64 * 1024 * 1024;
  let events = [],
    current = [],
    nodes = new Map(),
    edges = [],
    nodeEls = new Map();
  let selectedId = null,
    mode = "flow",
    scale = 1,
    tx = 120,
    ty = 100;
  let page = 0,
    playing = null,
    watchedHandle = null,
    watchTimer = null,
    importGeneration = 0;
  const positions = new Map();
  let filename = "",
    isDragging = null,
    toastTimeout,
    raf = 0;
  const demo = [
    {
      seq: 1,
      ms: 0,
      kind: "start",
      name: "Запуск Xopilot",
      detail: "main()",
      thread: "ThreadId(1)",
      id: "main",
    },
    {
      seq: 2,
      ms: 3,
      kind: "call",
      name: "initialize()",
      detail: "Инициализация приложения",
      thread: "ThreadId(1)",
      id: "init",
      parent_id: "main",
    },
    {
      seq: 3,
      ms: 5,
      kind: "file_write",
      name: "Запись файла",
      detail: "/tmp/xopilot-demo.txt",
      thread: "ThreadId(1)",
      id: "write",
      parent_id: "init",
    },
    {
      seq: 4,
      ms: 7,
      kind: "step",
      name: "Файл записан",
      detail: "21 байт, 2 мс",
      thread: "ThreadId(1)",
      id: "written",
      parent_id: "write",
    },
    {
      seq: 5,
      ms: 8,
      kind: "file_read",
      name: "Чтение файла",
      detail: "/tmp/xopilot-demo.txt",
      thread: "ThreadId(1)",
      id: "read",
      parent_id: "init",
    },
    {
      seq: 6,
      ms: 9,
      kind: "step",
      name: "Файл прочитан",
      detail: "21 байт, 1 мс",
      thread: "ThreadId(1)",
      id: "readok",
      parent_id: "read",
    },
    {
      seq: 7,
      ms: 10,
      kind: "variable",
      name: "testingss",
      detail: "21",
      thread: "ThreadId(1)",
      id: "value",
      parent_id: "init",
    },
    {
      seq: 8,
      ms: 11,
      kind: "branch",
      name: "testingss > 0",
      detail: "true",
      thread: "ThreadId(1)",
      id: "branch",
      parent_id: "init",
    },
    {
      seq: 9,
      ms: 12,
      kind: "call",
      name: "spawn_worker()",
      detail: "Запуск фоновой задачи",
      thread: "ThreadId(1)",
      id: "spawn",
      parent_id: "branch",
    },
    {
      seq: 10,
      ms: 14,
      kind: "call",
      name: "process_data()",
      detail: "Фоновый поток",
      thread: "ThreadId(2)",
      id: "worker",
      parent_id: "spawn",
    },
    {
      seq: 11,
      ms: 18,
      kind: "step",
      name: "Данные обработаны",
      detail: "Время 4 мс",
      thread: "ThreadId(2)",
      id: "done",
      parent_id: "worker",
    },
    {
      seq: 12,
      ms: 20,
      kind: "end",
      name: "Завершение",
      detail: "Успешно",
      thread: "ThreadId(1)",
      id: "end",
      parent_id: "main",
    },
  ];
  function element(tag, attrs = {}, text) {
    const node = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attrs))
      node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = String(text);
    return node;
  }
  const short = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
  const formatMs = (ms) =>
    ms >= 1000 ? `${(ms / 1000).toFixed(2)} с` : `${ms} мс`;
  const meta = (kind) =>
    KIND[kind] || { icon: "·", label: kind, stroke: "#9faec1", bg: "#2b3440" };
  function parseFile(text, partialTail = false) {
    return FlowmapModel.parse(text, { partialTail });
  }
  function message(content, kind = "") {
    const n = $("#notice");
    n.className = `notice ${kind}`;
    n.querySelector("span").textContent = content;
  }
  function toast(content) {
    toastBox.textContent = content;
    toastBox.classList.add("visible");
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => toastBox.classList.remove("visible"), 2600);
  }
  function setEvents(raw, origin) {
    events = raw;
    filename = origin;
    selectedId = null;
    page = 0;
    nodes.clear();
    positions.clear();
    stopPlayback();
    $("#search").value = "";
    $("#thread").value = "*";
    $("#kind").value = "*";
    populateFilters();
    refresh(true);
  }
  function populateFilters() {
    const thread = $("#thread"),
      kind = $("#kind");
    thread.replaceChildren(new Option("Все потоки", "*"));
    kind.replaceChildren(new Option("Все типы", "*"));
    [...new Set(events.map((e) => e.thread))]
      .sort()
      .forEach((t) => thread.add(new Option(short(t, 22), t)));
    [...new Set(events.map((e) => e.kind))]
      .sort()
      .forEach((k) => kind.add(new Option(meta(k).label, k)));
  }
  function visibleEvents() {
    const search = $("#search").value.trim().toLocaleLowerCase("ru");
    const thread = $("#thread").value,
      kind = $("#kind").value;
    const filtered = events.filter(
      (e) =>
        (thread === "*" || e.thread === thread) &&
        (kind === "*" || e.kind === kind) &&
        (!search ||
          [
            e.name,
            e.detail,
            e.kind,
            e.thread,
            e.file,
            e.session,
            e.id,
            String(e.seq),
          ].some((v) => v.toLocaleLowerCase("ru").includes(search))),
    );
    return {
      filtered,
      visible: filtered.slice(page * MAX_VISIBLE, (page + 1) * MAX_VISIBLE),
    };
  }
  function arrange(list) {
    nodes = new Map();
    if (mode === "flow") {
      const cols = 5,
        gapX = 318,
        gapY = 166;
      list.forEach((e, i) => {
        const row = Math.floor(i / cols),
          pos = i % cols,
          col = row % 2 === 0 ? pos : cols - 1 - pos;
        nodes.set(e.id, { event: e, x: 80 + col * gapX, y: 78 + row * gapY });
      });
    } else {
      const lanes = [...new Set(list.map((e) => e.thread))];
      const counters = new Map();
      list.forEach((e) => {
        const lane = lanes.indexOf(e.thread),
          col = counters.get(lane) || 0;
        nodes.set(e.id, { event: e, x: 80 + col * 315, y: 78 + lane * 208 });
        counters.set(lane, col + 1);
      });
    }
  }
  function rememberPositions() {
    for (const [id, node] of nodes)
      positions.set(`${mode}/${id}`, { x: node.x, y: node.y });
  }
  function computeEdges() {
    const byId = new Map(events.map((e) => [e.id, e]));
    const previous = new Map();
    const seenEdges = new Set();
    edges = [];
    for (const e of events) {
      const lane = e.session + "/" + e.thread;
      const pred = previous.get(lane);
      if (pred && nodes.has(pred.id) && nodes.has(e.id)) {
        const key = `${pred.id}|${e.id}|temporal`;
        if (!seenEdges.has(key)) {
          edges.push({
            from: pred.id,
            to: e.id,
            kind: "temporal",
            label: pred.kind === "branch" ? pred.detail : "",
          });
          seenEdges.add(key);
        }
      }
      previous.set(lane, e);
      if (
        e.parent &&
        byId.has(e.parent) &&
        nodes.has(e.parent) &&
        nodes.has(e.id) &&
        e.parent !== e.id
      ) {
        const key = `${e.parent}|${e.id}|causal`;
        if (!seenEdges.has(key)) {
          edges.push({ from: e.parent, to: e.id, kind: "causal", label: "" });
          seenEdges.add(key);
        }
      }
    }
  }
  function text(parent, x, y, txt, attrs = {}) {
    parent.append(
      element(
        "text",
        {
          x,
          y,
          fill: "#d9e6f1",
          "font-size": 12,
          class: "node-text",
          ...attrs,
        },
        txt,
      ),
    );
  }
  function createNode(p) {
    const e = p.event,
      m = meta(e.kind);
    const g = element("g", {
      class: "node",
      transform: `translate(${p.x},${p.y})`,
      tabindex: 0,
      role: "button",
      "aria-label": `${e.name}. ${meta(e.kind).label}. ${formatMs(e.ms)}`,
    });
    const rect = element("rect", {
      class: "node-card",
      width: NODE_W,
      height: NODE_H,
      rx: 13,
      fill: "#202a35",
      stroke: "#405163",
      "stroke-width": 1.4,
    });
    g.append(rect);
    g.append(
      element("rect", {
        x: 1,
        y: 1,
        width: 5,
        height: NODE_H - 2,
        rx: 2,
        fill: m.stroke,
      }),
    );
    g.append(
      element("rect", {
        x: 14,
        y: 12,
        width: 33,
        height: 33,
        rx: 9,
        fill: m.bg,
        stroke: m.stroke,
        "stroke-opacity": ".65",
      }),
    );
    text(g, 30, 34, m.icon, {
      "font-size": 18,
      "font-weight": 700,
      fill: m.stroke,
      "text-anchor": "middle",
    });
    text(g, 57, 24, short(m.label.toUpperCase(), 15), {
      "font-size": 10,
      "font-weight": 700,
      fill: m.stroke,
      "letter-spacing": ".7",
    });
    text(g, NODE_W - 13, 24, formatMs(e.ms), {
      "font-size": 10,
      fill: "#8fa4b5",
      "text-anchor": "end",
    });
    text(g, 16, 63, short(e.name, 34), { "font-size": 14, "font-weight": 650 });
    text(g, 16, 83, short(e.detail || `#${e.seq} · ${e.thread}`, 39), {
      "font-size": 11,
      fill: "#9badbf",
    });
    g.append(
      element("circle", {
        class: "node-port",
        cx: 0,
        cy: 49,
        r: 6,
        fill: "#111922",
        stroke: "#8799a9",
        "stroke-width": 1.7,
      }),
    );
    if (e.kind === "branch") {
      for (const [y, label] of [
        [29, "T"],
        [72, "F"],
      ]) {
        const active =
          e.detail.trim().toLowerCase() === (label === "T" ? "true" : "false");
        g.append(
          element("circle", {
            class: "node-port",
            cx: NODE_W,
            cy: y,
            r: 6,
            fill: active ? m.stroke : "#283340",
            stroke: active ? m.stroke : "#8799a9",
            "stroke-width": 1.5,
          }),
        );
        text(g, NODE_W - 14, y + 4, label, {
          "font-size": 10,
          "font-weight": 700,
          "text-anchor": "end",
          fill: active ? m.stroke : "#8192a4",
        });
      }
    } else
      g.append(
        element("circle", {
          class: "node-port",
          cx: NODE_W,
          cy: 49,
          r: 6,
          fill: "#131b23",
          stroke: m.stroke,
          "stroke-width": 1.7,
        }),
      );
    g.addEventListener("pointerdown", (ev) => startDraggingNode(ev, e.id));
    g.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        select(e.id);
      }
    });
    if (e.id === selectedId) g.classList.add("selected");
    return g;
  }
  function edgeGeometry(edge) {
    const from = nodes.get(edge.from),
      to = nodes.get(edge.to);
    if (!from || !to) return null;
    const b1 = from.x + NODE_W / 2,
      b2 = to.x + NODE_W / 2;
    const dx = b2 - b1,
      dy = to.y - from.y;
    let x1,
      y1,
      x2,
      y2,
      offset = 65,
      axis = "x";
    const sameRow = Math.abs(dy) < 100;
    if (sameRow && Math.abs(dx) > 120) {
      const right = dx >= 0;
      x1 = right ? from.x + NODE_W : from.x;
      x2 = right ? to.x : to.x + NODE_W;
      y1 =
        from.y +
        (from.event.kind === "branch"
          ? from.event.detail === "false"
            ? 72
            : 29
          : 49);
      y2 = to.y + 49;
      offset = right
        ? Math.max(50, Math.abs(x2 - x1) / 2)
        : -Math.max(50, Math.abs(x2 - x1) / 2);
    } else {
      axis = "y";
      x1 = from.x + NODE_W / 2;
      x2 = to.x + NODE_W / 2;
      y1 = from.y + NODE_H;
      y2 = to.y;
      if (y2 < y1) {
        y1 = from.y;
        y2 = to.y + NODE_H;
      }
      offset = (y2 >= y1 ? 1 : -1) * Math.max(40, Math.abs(y2 - y1) / 2);
    }
    const d =
      axis === "x"
        ? `M ${x1} ${y1} C ${x1 + offset} ${y1}, ${x2 - offset} ${y2}, ${x2} ${y2}`
        : `M ${x1} ${y1} C ${x1} ${y1 + offset}, ${x2} ${y2 - offset}, ${x2} ${y2}`;
    return { d, x1, y1, x2, y2, mx: (x1 + x2) / 2, my: (y1 + y2) / 2 };
  }
  function renderEdges() {
    const fragment = document.createDocumentFragment();
    edges.forEach((edge) => {
      const geo = edgeGeometry(edge);
      if (!geo) return;
      const path = element("path", {
        d: geo.d,
        class: `edge ${edge.kind}`,
        stroke: edge.kind === "causal" ? "#69c4aa" : "#64798c",
        "stroke-width": edge.kind === "causal" ? 2.3 : 1.7,
        fill: "none",
        "stroke-dasharray": edge.kind === "temporal" ? "7 7" : "none",
        "marker-end": `url(#arrow-${edge.kind === "causal" ? "causal" : "time"})`,
      });
      fragment.append(path);
      if (edge.label === "true" || edge.label === "false") {
        const group = element("g", {});
        group.append(
          element("rect", {
            x: geo.mx - 18,
            y: geo.my - 18,
            width: 36,
            height: 20,
            rx: 5,
            fill: "#282f2b",
            stroke: "#9d8354",
          }),
        );
        group.append(
          element(
            "text",
            {
              x: geo.mx,
              y: geo.my - 4,
              "text-anchor": "middle",
              fill: "#e7bf7c",
              "font-size": 10,
            },
            edge.label,
          ),
        );
        fragment.append(group);
      }
    });
    edgesLayer.replaceChildren(fragment);
  }
  function renderNodes() {
    nodeEls = new Map();
    const fragment = document.createDocumentFragment();
    for (const [id, p] of nodes) {
      const g = createNode(p);
      fragment.append(g);
      nodeEls.set(id, g);
    }
    nodesLayer.replaceChildren(fragment);
    $("#empty").hidden = nodes.size > 0;
    $("#minimap").hidden = !nodes.size;
  }
  function setTransform() {
    viewport.setAttribute(
      "transform",
      `translate(${tx} ${ty}) scale(${scale})`,
    );
    $("#zoom-label").textContent = `${Math.round(scale * 100)}%`;
    shell.style.backgroundPosition = `${tx % 24}px ${ty % 24}px`;
    scheduleMinimap();
  }
  function bounds() {
    if (!nodes.size)
      return {
        left: 0,
        top: 0,
        right: 100,
        bottom: 100,
        width: 100,
        height: 100,
      };
    let left = Infinity,
      top = Infinity,
      right = -Infinity,
      bottom = -Infinity;
    for (const p of nodes.values()) {
      left = Math.min(left, p.x);
      top = Math.min(top, p.y);
      right = Math.max(right, p.x + NODE_W);
      bottom = Math.max(bottom, p.y + NODE_H);
    }
    return {
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top,
    };
  }
  function fit() {
    if (!nodes.size) return;
    const b = bounds(),
      w = shell.clientWidth || 900,
      h = shell.clientHeight || 500,
      pad = 80;
    scale = Math.min(
      1.25,
      Math.max(0.02, Math.min((w - pad) / b.width, (h - pad) / b.height)),
    );
    tx = (w - scale * b.width) / 2 - scale * b.left;
    ty = (h - scale * b.height) / 2 - scale * b.top;
    setTransform();
  }
  function zoomAt(next, x, y) {
    next = Math.min(2.5, Math.max(0.02, next));
    const wx = (x - tx) / scale,
      wy = (y - ty) / scale;
    scale = next;
    tx = x - wx * scale;
    ty = y - wy * scale;
    setTransform();
  }
  function centerNode(id) {
    const p = nodes.get(id);
    if (!p) return;
    tx = shell.clientWidth / 2 - (p.x + NODE_W / 2) * scale;
    ty = shell.clientHeight / 2 - (p.y + NODE_H / 2) * scale;
    setTransform();
  }
  function select(id, focus = false) {
    if (!nodes.has(id)) return;
    selectedId = id;
    for (const [nodeId, g] of nodeEls)
      g.classList.toggle("selected", nodeId === id);
    const event = nodes.get(id).event;
    const duration =
      event.duration_ms ??
      events.find((item) => item.kind === "end" && item.parent === event.id)
        ?.duration_ms;
    details.replaceChildren();
    const m = meta(event.kind);
    const icon = document.createElement("div");
    icon.className = "info-icon";
    icon.textContent = m.icon;
    icon.style.color = m.stroke;
    details.append(icon);
    const title = document.createElement("h3");
    title.className = "info-title";
    title.textContent = event.name;
    details.append(title);
    const subtitle = document.createElement("p");
    subtitle.className = "info-sub";
    subtitle.textContent = `${m.label} · #${event.seq}`;
    details.append(subtitle);
    const section = document.createElement("section");
    section.className = "info-section";
    const h = document.createElement("h3");
    h.textContent = "Событие";
    section.append(h);
    const dl = document.createElement("dl");
    for (const [label, value] of [
      ["От старта", formatMs(event.ms)],
      ["Поток", event.thread],
      ["Тип", event.kind],
      ["Идентификатор", event.id],
      ["Родитель", event.parent || "—"],
      ["Сессия", event.session],
      [
        "Исходник",
        event.file
          ? `${event.file}:${event.line ?? "?"}:${event.column ?? "?"}`
          : "—",
      ],
      ["Длительность", duration == null ? "—" : formatMs(Number(duration))],
    ]) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = String(value);
      dl.append(dt, dd);
    }
    if (
      event.parent &&
      !nodes.has(event.parent) &&
      events.some((item) => item.id === event.parent)
    ) {
      const parentButton = document.createElement("button");
      parentButton.className = "link-chip";
      parentButton.textContent = "Показать родительскую операцию";
      parentButton.addEventListener("click", () => {
        stopPlayback();
        $("#search").value = "";
        $("#thread").value = "*";
        $("#kind").value = "*";
        page = Math.floor(
          events.findIndex((item) => item.id === event.parent) / MAX_VISIBLE,
        );
        refresh(true);
        select(event.parent, true);
      });
      section.append(parentButton);
    }
    section.append(dl);
    details.append(section);
    if (event.detail) {
      const box = document.createElement("section");
      box.className = "info-section";
      const heading = document.createElement("h3");
      heading.textContent = "Значение / описание";
      box.append(heading);
      const body = document.createElement("div");
      body.className = "detail";
      body.textContent = event.detail;
      box.append(body);
      details.append(box);
    }
    const outgoing = edges.filter((e) => e.from === id),
      incoming = edges.filter((e) => e.to === id);
    if (outgoing.length || incoming.length) {
      const box = document.createElement("section");
      box.className = "info-section";
      const heading = document.createElement("h3");
      heading.textContent = "Связи";
      box.append(heading);
      for (const edge of [...incoming, ...outgoing].slice(0, 16)) {
        const targetId = edge.from === id ? edge.to : edge.from;
        const target = nodes.get(targetId);
        if (!target) continue;
        const button = document.createElement("button");
        button.className = "link-chip";
        button.textContent = `${edge.from === id ? "↗" : "↙"} ${short(target.event.name, 22)} · ${edge.kind === "causal" ? "parent" : "время"}`;
        button.addEventListener("click", () => select(targetId, true));
        box.append(button);
      }
      details.append(box);
    }
    document
      .querySelectorAll(".time-card")
      .forEach((button) =>
        button.classList.toggle("active", button.dataset.id === id),
      );
    if (focus) centerNode(id);
  }
  function renderTimeline() {
    const container = $("#timeline-items"),
      frag = document.createDocumentFragment();
    for (const e of current) {
      const b = document.createElement("button");
      b.className = `time-card${e.id === selectedId ? " active" : ""}`;
      b.dataset.id = e.id;
      b.style.borderTop = `3px solid ${meta(e.kind).stroke}`;
      const strong = document.createElement("strong");
      strong.textContent = e.name;
      const small = document.createElement("small");
      small.textContent = `#${e.seq} · ${formatMs(e.ms)} · ${meta(e.kind).label}`;
      b.append(strong, small);
      b.addEventListener("click", () => select(e.id, true));
      frag.append(b);
    }
    if (!current.length) {
      const empty = document.createElement("span");
      empty.className = "time-empty";
      empty.textContent = "Нет событий";
      frag.append(empty);
    }
    container.replaceChildren(frag);
    $("#timeline-caption").textContent = "Нажми на событие для перехода";
  }
  function refresh(resetLayout = false) {
    rememberPositions();
    const total = visibleEvents().filtered.length;
    page = Math.min(page, Math.max(0, Math.ceil(total / MAX_VISIBLE) - 1));
    const { filtered, visible } = visibleEvents();
    current = visible;
    $("#page-label").textContent =
      `${page + 1} / ${Math.max(1, Math.ceil(total / MAX_VISIBLE))}`;
    $("#page-prev").disabled = page === 0;
    $("#page-next").disabled = (page + 1) * MAX_VISIBLE >= total;
    if (selectedId && !visible.some((e) => e.id === selectedId))
      selectedId = null;
    arrange(visible);
    for (const [id, node] of nodes)
      Object.assign(node, positions.get(`${mode}/${id}`) || {});
    computeEdges();
    renderEdges();
    renderNodes();
    renderTimeline();
    if (resetLayout) fit();
    else setTransform();
    const threads = new Set(visible.map((e) => e.thread)).size;
    $("#stats").textContent =
      `${filename || "Данные"} · ${events.length} событий · показано ${visible.length} · потоков ${threads} · связей ${edges.length}`;
    if (!events.length)
      message("Открой трассировку Xopilot или нажми «Пример».");
    else if (filtered.length > MAX_VISIBLE)
      message(
        `События ${page * MAX_VISIBLE + 1}–${page * MAX_VISIBLE + visible.length} из ${filtered.length}. Используй страницы или фильтры.`,
        "warning",
      );
    else if (!visible.length)
      message("Ничего не найдено по выбранному фильтру.", "warning");
    else
      message(
        `${filename || "Трассировка"} · ${visible.length} событий. Пунктир — порядок, сплошная стрелка — явный parent_id.`,
      );
    if (selectedId) select(selectedId);
    else
      details.replaceChildren(
        Object.assign(document.createElement("div"), {
          className: "placeholder",
          textContent:
            "Выбери ноду на графе. Здесь появятся данные события, его поток, время и связи.",
        }),
      );
  }
  function startDraggingNode(ev, id) {
    if (ev.button !== 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    shell.focus({ preventScroll: true });
    const p = nodes.get(id);
    if (!p) return;
    isDragging = {
      type: "node",
      id,
      x: ev.clientX,
      y: ev.clientY,
      origX: p.x,
      origY: p.y,
      moved: false,
    };
    shell.setPointerCapture(ev.pointerId);
  }
  shell.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0 || isDragging) return;
    if (ev.target.closest("#empty, #minimap, button, input, select, label"))
      return;
    isDragging = {
      type: "pan",
      x: ev.clientX,
      y: ev.clientY,
      origX: tx,
      origY: ty,
      moved: false,
    };
    shell.classList.add("grabbing");
    shell.setPointerCapture(ev.pointerId);
  });
  shell.addEventListener("pointermove", (ev) => {
    if (!isDragging) return;
    const dx = ev.clientX - isDragging.x,
      dy = ev.clientY - isDragging.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) isDragging.moved = true;
    if (isDragging.type === "pan") {
      tx = isDragging.origX + dx;
      ty = isDragging.origY + dy;
      setTransform();
    } else {
      const p = nodes.get(isDragging.id);
      if (!p) return;
      p.x = isDragging.origX + dx / scale;
      p.y = isDragging.origY + dy / scale;
      nodeEls
        .get(isDragging.id)
        ?.setAttribute("transform", `translate(${p.x},${p.y})`);
      renderEdges();
      scheduleMinimap();
    }
  });
  function endPointer(ev) {
    if (!isDragging) return;
    if (isDragging.type === "node" && !isDragging.moved) select(isDragging.id);
    isDragging = null;
    shell.classList.remove("grabbing");
    if (shell.hasPointerCapture(ev.pointerId))
      shell.releasePointerCapture(ev.pointerId);
  }
  shell.addEventListener("pointerup", endPointer);
  shell.addEventListener("pointercancel", endPointer);
  shell.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      const rect = shell.getBoundingClientRect();
      zoomAt(
        scale * Math.exp(-ev.deltaY * 0.0012),
        ev.clientX - rect.left,
        ev.clientY - rect.top,
      );
    },
    { passive: false },
  );
  function scheduleMinimap() {
    if (!raf)
      raf = requestAnimationFrame(() => {
        raf = 0;
        drawMinimap();
      });
  }
  function drawMinimap() {
    const canvas = $("#mini-canvas");
    const w = canvas.clientWidth,
      h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!nodes.size) return;
    const b = bounds(),
      pad = 15,
      f = Math.min(
        (w - 2 * pad) / Math.max(1, b.width),
        (h - 2 * pad) / Math.max(1, b.height),
      );
    const offsetX = (w - b.width * f) / 2 - b.left * f,
      offsetY = (h - b.height * f) / 2 - b.top * f;
    ctx.strokeStyle = "#465361";
    ctx.lineWidth = 1;
    edges.forEach((edge) => {
      const a = nodes.get(edge.from),
        b2 = nodes.get(edge.to);
      if (!a || !b2) return;
      ctx.beginPath();
      ctx.moveTo(
        (a.x + NODE_W / 2) * f + offsetX,
        (a.y + NODE_H / 2) * f + offsetY,
      );
      ctx.lineTo(
        (b2.x + NODE_W / 2) * f + offsetX,
        (b2.y + NODE_H / 2) * f + offsetY,
      );
      ctx.stroke();
    });
    for (const [id, p] of nodes) {
      ctx.fillStyle = id === selectedId ? "#7af6c9" : meta(p.event.kind).stroke;
      ctx.fillRect(
        p.x * f + offsetX,
        p.y * f + offsetY,
        Math.max(5, NODE_W * f),
        Math.max(3, NODE_H * f),
      );
    }
    const left = (-tx / scale) * f + offsetX,
      top = (-ty / scale) * f + offsetY;
    const viewW = (shell.clientWidth / scale) * f,
      viewH = (shell.clientHeight / scale) * f;
    ctx.strokeStyle = "#e6f4ff";
    ctx.fillStyle = "#9ec6dc14";
    ctx.lineWidth = 1.5;
    ctx.fillRect(left, top, viewW, viewH);
    ctx.strokeRect(left, top, viewW, viewH);
    canvas.dataset.map = JSON.stringify({ f, offsetX, offsetY });
  }
  $("#minimap").addEventListener("click", (ev) => {
    const canvas = $("#mini-canvas");
    const info = JSON.parse(canvas.dataset.map || "null");
    if (!info) return;
    const r = canvas.getBoundingClientRect(),
      x = (ev.clientX - r.left - info.offsetX) / info.f,
      y = (ev.clientY - r.top - info.offsetY) / info.f;
    tx = shell.clientWidth / 2 - x * scale;
    ty = shell.clientHeight / 2 - y * scale;
    setTransform();
  });
  function saveSVG() {
    if (!nodes.size) {
      toast("Сначала открой граф");
      return;
    }
    const b = bounds(),
      pad = 55;
    const clone = svg.cloneNode(true);
    clone.setAttribute("xmlns", svgNS);
    clone.setAttribute("width", b.width + pad * 2);
    clone.setAttribute("height", b.height + pad * 2);
    clone.setAttribute(
      "viewBox",
      `${b.left - pad} ${b.top - pad} ${b.width + 2 * pad} ${b.height + 2 * pad}`,
    );
    clone.querySelector("#viewport").setAttribute("transform", "");
    clone
      .querySelectorAll(".node-text")
      .forEach((text) => text.setAttribute("font-family", "sans-serif"));
    clone.querySelectorAll(".selected .node-card").forEach((rect) => {
      rect.setAttribute("stroke", "#54f3c5");
      rect.setAttribute("stroke-width", "2.7");
    });
    const bg = element("rect", {
      x: b.left - pad,
      y: b.top - pad,
      width: b.width + 2 * pad,
      height: b.height + 2 * pad,
      fill: "#101820",
    });
    clone.insertBefore(bg, clone.firstChild);
    const data =
      '<?xml version="1.0" encoding="UTF-8"?>\n' +
      new XMLSerializer().serializeToString(clone);
    const blob = new Blob([data], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `flowmap-${Date.now()}.svg`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("SVG сохранён");
  }
  async function loadFile(file) {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      message("Файл больше 64 МиБ. Сократи трассировку.", "error");
      return;
    }
    const generation = ++importGeneration;
    try {
      const parsed = parseFile(await file.text());
      if (generation !== importGeneration) return;
      stopWatch();
      setEvents(parsed, file.name);
      toast(`Загружено ${parsed.length} событий`);
    } catch (error) {
      message(`Ошибка импорта: ${error.message}`, "error");
      toast("Не удалось прочитать файл");
    }
  }
  $("#trace-file").addEventListener("change", (ev) => {
    loadFile(ev.target.files?.[0]);
    ev.target.value = "";
  });
  shell.addEventListener("dragover", (ev) => {
    if (ev.dataTransfer?.types.includes("Files")) ev.preventDefault();
  });
  shell.addEventListener("drop", (ev) => {
    ev.preventDefault();
    loadFile(ev.dataTransfer?.files[0]);
  });
  $("#demo-btn").addEventListener("click", () => {
    stopWatch();
    setEvents(
      parseFile(demo.map((x) => JSON.stringify(x)).join("\n")),
      "Демонстрация",
    );
  });
  $("#empty-demo").addEventListener("click", () => $("#demo-btn").click());
  $("#export-btn").addEventListener("click", saveSVG);
  $("#fit-btn").addEventListener("click", fit);
  $("#zoom-in").addEventListener("click", () =>
    zoomAt(scale * 1.2, shell.clientWidth / 2, shell.clientHeight / 2),
  );
  $("#zoom-out").addEventListener("click", () =>
    zoomAt(scale / 1.2, shell.clientWidth / 2, shell.clientHeight / 2),
  );
  $("#layout-btn").addEventListener("click", () => {
    rememberPositions();
    nodes.clear();
    mode = mode === "flow" ? "threads" : "flow";
    $("#layout-btn").textContent =
      mode === "flow" ? "⇄ По потокам" : "⇄ Общая схема";
    refresh(true);
  });
  for (const id of ["#search", "#kind", "#thread"])
    $(id).addEventListener(id === "#search" ? "input" : "change", () => {
      page = 0;
      stopPlayback();
      refresh(true);
    });
  window.addEventListener("keydown", (ev) => {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || ""))
      return;
    if (ev.key === "f" || ev.key === "F") {
      ev.preventDefault();
      fit();
    }
    if (ev.key === "Escape") {
      selectedId = null;
      refresh(false);
    }
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      stopPlayback();
      advance(1);
    }
    if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      stopPlayback();
      advance(-1);
    }
    if (ev.key === "/") {
      ev.preventDefault();
      $("#search").focus();
    }
    if (ev.key === "+" || ev.key === "=")
      zoomAt(scale * 1.2, shell.clientWidth / 2, shell.clientHeight / 2);
    if (ev.key === "-")
      zoomAt(scale / 1.2, shell.clientWidth / 2, shell.clientHeight / 2);
  });
  window.addEventListener("resize", () => {
    setTransform();
  });

  // Единая загрузка Blob для трассы и раскладки. Значения остаются в локальном файле.
  function download(data, name, type = "application/json") {
    const url = URL.createObjectURL(new Blob([data], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function stopPlayback() {
    if (playing) clearInterval(playing);
    playing = null;
    $("#play-btn").textContent = "▶ Просмотр";
  }
  function advance(delta) {
    const filtered = visibleEvents().filtered;
    if (!filtered.length) return false;
    const index = filtered.findIndex((event) => event.id === selectedId);
    const next = index < 0 ? 0 : index + delta;
    if (next < 0 || next >= filtered.length) return false;
    const target = filtered[next];
    if (Math.floor(next / MAX_VISIBLE) !== page) {
      page = Math.floor(next / MAX_VISIBLE);
      refresh(true);
    }
    select(target.id, true);
    return true;
  }
  function stopWatch() {
    if (watchTimer) clearTimeout(watchTimer);
    watchTimer = null;
    watchedHandle = null;
    $("#watch-btn").textContent = "Обновлять файл";
  }
  async function watchFile() {
    if (watchedHandle) {
      stopWatch();
      return;
    }
    try {
      let handle;
      const status = await fetch("/flowmap-status")
        .then((response) => (response.ok ? response.json() : {}))
        .catch(() => ({}));
      if (status.trace) {
        handle = {
          async getFile() {
            const response = await fetch("/flowmap-trace", {
              cache: "no-store",
            });
            if (!response.ok)
              throw Error("Не удалось прочитать подключённую трассу");
            const content = await response.text();
            return {
              name: status.trace,
              size: new TextEncoder().encode(content).byteLength,
              lastModified: response.headers.get("X-Flowmap-Revision"),
              text: async () => content,
            };
          },
        };
      } else {
        if (!window.showOpenFilePicker) {
          toast(
            "Укажи журнал при запуске serve.cjs или открой файл в Chrome/Edge",
          );
          return;
        }
        [handle] = await window.showOpenFilePicker();
      }
      const file = await handle.getFile();
      if (file.size > MAX_BYTES) throw Error("Файл больше 64 МиБ");
      setEvents(parseFile(await file.text(), true), file.name);
      watchedHandle = handle;
      $("#watch-btn").textContent = "■ Остановить обновление";
      let lastModified = file.lastModified,
        lastSize = file.size;
      const poll = async () => {
        if (watchedHandle !== handle) return;
        try {
          const next = await handle.getFile();
          if (next.size > MAX_BYTES) throw Error("Файл больше 64 МиБ");
          if (next.lastModified !== lastModified || next.size !== lastSize) {
            const parsed = parseFile(await next.text(), true);
            if (watchedHandle !== handle) return;
            events = parsed;
            lastModified = next.lastModified;
            lastSize = next.size;
            const thread = $("#thread").value,
              kind = $("#kind").value;
            populateFilters();
            $("#thread").value = thread;
            $("#kind").value = kind;
            if (!$("#thread").value) $("#thread").value = "*";
            if (!$("#kind").value) $("#kind").value = "*";
            refresh();
          }
          if (watchedHandle === handle) watchTimer = setTimeout(poll, 1000);
        } catch (error) {
          stopWatch();
          message(error.message, "error");
        }
      };
      watchTimer = setTimeout(poll, 1000);
    } catch (error) {
      if (error.name !== "AbortError") message(error.message, "error");
    }
  }
  $("#watch-btn").addEventListener("click", watchFile);
  $("#json-btn").addEventListener("click", () =>
    download(
      events.map((event) => JSON.stringify(event.raw)).join("\n") + "\n",
      "flowmap.jsonl",
      "application/x-ndjson",
    ),
  );
  $("#save-layout").addEventListener("click", () => {
    rememberPositions();
    download(
      JSON.stringify({ version: 1, mode, positions: [...positions] }, null, 2),
      "flowmap-layout.json",
    );
  });
  $("#layout-file").addEventListener("change", async (event) => {
    try {
      const file = event.target.files[0];
      if (!file) return;
      if (file.size > 8 * 1024 * 1024) throw Error("Раскладка больше 8 МиБ");
      const layout = JSON.parse(await file.text());
      if (
        layout.version !== 1 ||
        !["flow", "threads"].includes(layout.mode) ||
        !Array.isArray(layout.positions) ||
        layout.positions.length > 200000
      )
        throw Error("Неверная раскладка");
      const validated = new Map();
      for (const entry of layout.positions) {
        if (!Array.isArray(entry) || entry.length !== 2)
          throw Error("Неверная позиция");
        const [id, p] = entry;
        if (
          typeof id !== "string" ||
          !p ||
          !Number.isFinite(p.x) ||
          !Number.isFinite(p.y) ||
          Math.abs(p.x) > 1e7 ||
          Math.abs(p.y) > 1e7
        )
          throw Error("Неверные координаты");
        validated.set(id, { x: p.x, y: p.y });
      }
      nodes.clear();
      positions.clear();
      for (const [id, p] of validated) positions.set(id, p);
      mode = layout.mode;
      refresh(true);
      toast("Раскладка восстановлена");
    } catch (error) {
      message(error.message, "error");
    }
    event.target.value = "";
  });
  $("#page-prev").addEventListener("click", () => {
    page--;
    stopPlayback();
    refresh(true);
  });
  $("#page-next").addEventListener("click", () => {
    page++;
    stopPlayback();
    refresh(true);
  });
  $("#step-prev").addEventListener("click", () => {
    stopPlayback();
    advance(-1);
  });
  $("#step-next").addEventListener("click", () => {
    stopPlayback();
    advance(1);
  });
  $("#play-btn").addEventListener("click", () => {
    if (playing) {
      stopPlayback();
      return;
    }
    $("#play-btn").textContent = "⏸ Пауза";
    if (!advance(1)) {
      selectedId = null;
      advance(1);
    }
    playing = setInterval(() => {
      if (!advance(1)) stopPlayback();
    }, 500);
  });
  window.addEventListener("pagehide", () => {
    stopPlayback();
    stopWatch();
  });
  refresh(true);
})();
