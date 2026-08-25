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
  ".mp4": "video/mp4",
};

http
  .createServer((req, res) => {
    let rel = decodeURIComponent(req.url.split("?")[0]);
    if (rel === "/") rel = "/index.html";

    // Mirror the rewrites in vercel.json so pretty permalinks behave the same
    // locally as in production. Without this, /product/<slug>/ 404s here and the
    // canonical URLs look broken in dev while being fine on the deployed site.
    if (/^\/product\/[^/]+\/?$/.test(rel)) rel = "/product.html";
    else if (/^\/product-category\/[^/]+\/?$/.test(rel)) rel = "/category.html";
    else if (/^\/shop\/?$/.test(rel)) rel = "/category.html";

    // keep requests inside the project directory
    const file = path.join(ROOT, path.normalize(rel).replace(/^(\.\.[\\/])+/, ""));
    if (!file.startsWith(ROOT)) {
      res.writeHead(403).end("Forbidden");
      return;
    }

    // The hero reel needs byte ranges: Chrome will play a bare 200, but Safari and iOS
    // refuse a <video> served without range support, so local testing would say the
    // reel is broken when only this server is. Vercel serves ranges in production.
    const stat = fs.statSync(file, { throwIfNoEntry: false });
    const range = stat && req.headers.range && /^bytes=\d*-\d*$/.test(req.headers.range)
      ? req.headers.range.slice(6).split("-")
      : null;
    if (range) {
      const start = range[0] ? Number(range[0]) : 0;
      const end = range[1] ? Math.min(Number(range[1]), stat.size - 1) : stat.size - 1;
      if (start > end || start >= stat.size) {
        res.writeHead(416, { "Content-Range": "bytes */" + stat.size }).end();
        return;
      }
      res.writeHead(206, {
        "Content-Type": TYPES[path.extname(file).toLowerCase()] || "application/octet-stream",
        "Content-Length": end - start + 1,
        "Content-Range": "bytes " + start + "-" + end + "/" + stat.size,
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
      });
      fs.createReadStream(file, { start, end }).pipe(res);
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
        "Accept-Ranges": "bytes",
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
