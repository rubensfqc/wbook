// Copies vendored JS from node_modules into static/vendor (no CDN JavaScript in production).
const fs = require("fs");
const path = require("path");
const copies = [
  ["node_modules/htmx.org/dist/htmx.min.js", "static/vendor/htmx/htmx.min.js"],
  ["node_modules/chart.js/dist/chart.umd.js", "static/vendor/chartjs/chart.umd.min.js"],
];
for (const [src, dst] of copies) {
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  // drop sourceMappingURL comments: the .map files are not vendored and collectstatic would fail on them
  const body = fs.readFileSync(src, "utf8").replace(/\/\/# sourceMappingURL=.*$/gm, "");
  fs.writeFileSync(dst, body);
  console.log("copied", dst);
}
