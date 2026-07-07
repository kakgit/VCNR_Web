const http = require("http");
const fs = require("fs");
const path = require("path");

const port = Number(process.env.PORT || 3000);
const rootDir = __dirname;

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".vcnr": "application/octet-stream",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
};

function safePathname(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const normalized = path.normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  return normalized === path.sep ? "index.html" : normalized.replace(/^[/\\]/, "");
}

function sendFile(filePath, response) {
  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const headers = {
      "Content-Type": mimeTypes[ext] || "application/octet-stream",
      "Content-Length": stats.size,
      "Cache-Control": ext === ".vcnr" ? "public, max-age=31536000, immutable" : "no-cache",
      "Access-Control-Allow-Origin": "*",
    };

    response.writeHead(200, headers);
    fs.createReadStream(filePath).pipe(response);
  });
}

const server = http.createServer((request, response) => {
  if (!request.url) {
    response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Bad request");
    return;
  }

  if (request.method === "OPTIONS") {
    response.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Range",
    });
    response.end();
    return;
  }

  let relativePath = safePathname(request.url);
  let filePath = path.join(rootDir, relativePath);

  if (!path.resolve(filePath).startsWith(path.resolve(rootDir))) {
    response.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Forbidden");
    return;
  }

  fs.stat(filePath, (error, stats) => {
    if (!error && stats.isDirectory()) {
      filePath = path.join(filePath, "index.html");
      sendFile(filePath, response);
      return;
    }

    if (!error && stats.isFile()) {
      sendFile(filePath, response);
      return;
    }

    sendFile(path.join(rootDir, "index.html"), response);
  });
});

server.listen(port, () => {
  console.log(`VCNR web player listening on port ${port}`);
});
