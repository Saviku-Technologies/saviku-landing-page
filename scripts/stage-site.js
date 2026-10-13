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
// The app reads https://saviku.co/legal/manifest.json and joins each url onto
// that directory. Repo urls are site-root paths (/legal/stays-terms/v3.html),
// so the copy served under /legal drops that prefix (/stays-terms/v3.html,
// /faq/v1.json). Leaving them unchanged would fetch /legal/legal/...
// The root /manifest.json keeps the /legal prefix on purpose; only the app's
// /legal/manifest.json copy is stripped, so read that one, not the root copy.
fs.mkdirSync(path.join(output, "legal"), { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));
for (const [key, meta] of Object.entries(manifest)) {
  if (!meta || typeof meta.url !== "string" || !meta.url.startsWith("/legal/")) {
    throw new Error(`manifest url for ${key} must be a /legal/ path, got ${meta && meta.url}`);
  }
  meta.url = meta.url.slice("/legal".length);
}
const faq = manifest.platform_faq;
if (!faq || !/^\/faq\/v\d+\.json$/.test(faq.url)) {
  throw new Error(`platform_faq url must be /faq/vN.json on the legal manifest, got ${faq && faq.url}`);
}
fs.writeFileSync(
  path.join(output, "legal", "manifest.json"),
  JSON.stringify(manifest, null, 2) + "\n",
);
fs.copyFileSync(path.join(root, "faq.json"), path.join(output, "legal", "faq.json"));
console.log("Static site packaged in dist/");
