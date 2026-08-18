/* Zero-dependency static dev server for the V2 templates.
   node build/dev-server.js [port]   (or: npm run dev) */
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PORT = Number(process.argv[2] || process.env.PORT || 8777);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

http
  .createServer((req, res) => {
    let rel = decodeURIComponent(req.url.split("?")[0]);
    if (rel === "/") rel = "/index.html";

    // keep requests inside the project directory
    const file = path.join(ROOT, path.normalize(rel).replace(/^(\.\.[\\/])+/, ""));
    if (!file.startsWith(ROOT)) {
      res.writeHead(403).end("Forbidden");
      return;
    }

    fs.readFile(file, (err, buf) => {
      if (err) {
        res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
        res.end(
          '<body style="background:#0b0c0d;color:#e9eaeb;font:16px system-ui;padding:40px">' +
            "<h1>404</h1><p>" + rel + "</p>" +
            '<p><a style="color:#e8431a" href="/index.html">index.html</a> · ' +
            '<a style="color:#e8431a" href="/category.html">category.html</a> · ' +
            '<a style="color:#e8431a" href="/product.html?id=1">product.html</a></p></body>'
        );
        return;
      }
      res.writeHead(200, {
        "Content-Type": TYPES[path.extname(file).toLowerCase()] || "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(buf);
    });
  })
  .listen(PORT, "127.0.0.1", () => {
    console.log("Texas Truck Parts V2 — dev server");
    console.log("  http://127.0.0.1:" + PORT + "/index.html     homepage");
    console.log("  http://127.0.0.1:" + PORT + "/category.html  shop / filters");
    console.log("  http://127.0.0.1:" + PORT + "/product.html?id=1  product detail");
    console.log("Ctrl+C to stop.");
  });
