// Локальная точка входа для браузера, включая File System Access в secure context.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const root = __dirname;
const tracePath = process.argv[2] ? path.resolve(process.argv[2]) : null;
const port = Number(process.env.FLOWMAP_PORT || 8787);
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};
const server = http.createServer(async (request, response) => {
  try {
    const name = decodeURIComponent(
      new URL(request.url, "http://localhost").pathname,
    );
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
    if (name === "/flowmap-trace" && tracePath) {
      // Читаем ограниченный снимок выбранного CLI-файла. При дописывании
      // остаток строки попадёт в следующий снимок, произвольных путей в URL нет.
      const file = await fs.promises.open(tracePath, "r");
      try {
        const stat = await file.stat();
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
