// Локальный каталог журналов и просмотрщик. Пути доступны только через каталог.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const root = __dirname;
const tracePath = process.argv[2] ? path.resolve(process.argv[2]) : null;
const traceDirectory = path.resolve(
  process.env.FLOWMAP_TRACE_DIR || path.join(root, "../../target/flow-traces"),
);
// Каталог обновляется при каждом запросе. Символические ссылки не включаем,
// выбранный CLI-файл также доступен, если он хранится вне стандартной папки.
async function catalogue() {
  const files = [];
  const entries = await fs.promises
    .readdir(traceDirectory, { withFileTypes: true })
    .catch((error) => {
      if (error.code === "ENOENT") return [];
      throw error;
    });
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".jsonl")) continue;
    const location = path.join(traceDirectory, entry.name);
    const stat = await fs.promises.lstat(location).catch(() => null);
    if (!stat?.isFile()) continue;
    files.push({
      id: Buffer.from(entry.name).toString("base64url"),
      name: entry.name,
      size: stat.size,
      modified: stat.mtimeMs,
      location,
    });
  }
  if (tracePath && !files.some((file) => file.location === tracePath)) {
    const stat = await fs.promises.lstat(tracePath).catch(() => null);
    if (stat?.isFile())
      files.push({
        id: "current",
        name: path.basename(tracePath),
        size: stat.size,
        modified: stat.mtimeMs,
        location: tracePath,
      });
  }
  return files.sort(
    (a, b) => b.modified - a.modified || a.name.localeCompare(b.name),
  );
}
const port = Number(process.env.FLOWMAP_PORT || 8787);
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://localhost");
    const name = decodeURIComponent(url.pathname);
    if (name === "/flowmap-status") {
      response.writeHead(200, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      });
      response.end(
        JSON.stringify({ trace: tracePath ? path.basename(tracePath) : null }),
      );
      return;
    }
    if (name === "/flowmap-files") {
      const files = await catalogue();
      response.writeHead(200, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      });
      response.end(
        JSON.stringify({
          files: files.map(({ location, ...file }) => file),
          selected:
            files.find((file) => file.location === tracePath)?.id ||
            files[0]?.id ||
            "",
        }),
      );
      return;
    }
    if (name === "/flowmap-trace") {
      const files = await catalogue();
      const id = url.searchParams.get("file");
      const selected = id
        ? files.find((file) => file.id === id)
        : files.find((file) => file.location === tracePath);
      if (!selected) throw Error("Журнал отсутствует в каталоге");
      // URL содержит только ID записи из каталога. Запрещаем подмену файла
      // символической ссылкой между чтением каталога и открытием снимка.
      const file = await fs.promises.open(
        selected.location,
        fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0),
      );
      try {
        const stat = await file.stat();
        if (!stat.isFile()) throw Error("Ожидается файл журнала");
        if (stat.size > 64 * 1024 * 1024) throw Error("Файл больше 64 МиБ");
        const buffer = Buffer.alloc(stat.size);
        let offset = 0;
        while (offset < buffer.length) {
          const { bytesRead } = await file.read(
            buffer,
            offset,
            buffer.length - offset,
            offset,
          );
          if (!bytesRead) break;
          offset += bytesRead;
        }
        response.writeHead(200, {
          "Content-Type": "application/x-ndjson; charset=utf-8",
          "Cache-Control": "no-store",
          "X-Flowmap-Revision": `${stat.mtimeMs}:${offset}`,
        });
        response.end(buffer.subarray(0, offset));
      } finally {
        await file.close();
      }
      return;
    }
    const file = path.resolve(
      root,
      "." + (name === "/" ? "/nodes.html" : name),
    );
    if (
      !file.startsWith(root + path.sep) ||
      !types[path.extname(file)] ||
      !fs.statSync(file).isFile()
    ) {
      response.writeHead(404);
      response.end("Not found");
      return;
    }
    response.writeHead(200, {
      "Content-Type": types[path.extname(file)],
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    fs.createReadStream(file).pipe(response);
  } catch (_) {
    response.writeHead(404);
    response.end("Not found");
  }
});
server.on("error", (error) => {
  console.error(error.message);
  process.exitCode = 1;
});
server.listen(port, "127.0.0.1", () =>
  console.log(`Flow Map: http://127.0.0.1:${server.address().port}`),
);
