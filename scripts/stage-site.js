// Package the static site without publishing repository or design files.
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const output = path.join(root, "dist");
fs.rmSync(output, { recursive: true, force: true });
fs.mkdirSync(output);
for (const name of fs.readdirSync(root).filter(name => name.endsWith(".html"))) {
  fs.copyFileSync(path.join(root, name), path.join(output, name));
}
for (const name of ["assets", "legal"]) {
  fs.cpSync(path.join(root, name), path.join(output, name), { recursive: true });
}
for (const name of ["_headers", "_redirects", "robots.txt", "sitemap.xml", "manifest.json", "faq.json"]) {
  fs.copyFileSync(path.join(root, name), path.join(output, name));
}
// The app reads https://saviku.co/legal/manifest.json (public_legal_base_url).
fs.mkdirSync(path.join(output, "legal"), { recursive: true });
fs.copyFileSync(path.join(root, "manifest.json"), path.join(output, "legal", "manifest.json"));
fs.copyFileSync(path.join(root, "faq.json"), path.join(output, "legal", "faq.json"));
console.log("Static site packaged in dist/");
