#!/usr/bin/env node
// Renders the CAD parts and assemblies to PNG with the same three.js code the website uses (MIT).
//   docs/assets/renders/<id>.png            transparent, for the website's part cards
//   docs/assets/readme/parts/<id>-{light,dark}.png   studio backdrop, for the README (<picture>)
// Usage: node tools/render.mjs   (needs Playwright with Chromium; `make renders`)
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { extname, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".stl": "model/stl", ".json": "application/json", ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml" };
const server = createServer(async (req, res) => {
  try {
    const p = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!p.startsWith(ROOT)) throw new Error("outside");
    res.writeHead(200, { "content-type": TYPES[extname(p)] || "application/octet-stream" }).end(await readFile(p));
  } catch { res.writeHead(404).end(); }
}).listen(0);
const base = `http://127.0.0.1:${server.address().port}/tools/render.html`;

const parts = Object.keys(JSON.parse(await readFile(join(ROOT, "cad/parts.json"), "utf8")).parts);
const jobs = [
  ...parts.map((id) => ({ id, w: 600, h: 600, bg: "none", el: 34, out: `docs/assets/renders/${id}.png` })),
  ...parts.flatMap((id) => ["light", "dark"].map((bg) => ({ id, w: 800, h: 800, bg, el: 34, out: `docs/assets/readme/parts/${id}-${bg}.png` }))),
  { id: "seedling_assembly", w: 1600, h: 1000, bg: "none", az: 20, el: 22, zoom: 0.62, tilt: 58, out: "docs/assets/renders/seedling_assembly.png" },
  ...["light", "dark"].flatMap((bg) => [
    { id: "seedling_assembly", w: 1600, h: 1000, bg, az: 20, el: 22, zoom: 0.62, tilt: 58, out: `docs/assets/readme/seedling-assembly-${bg}.png` },
    { id: "seedling_exploded", w: 900, h: 1300, bg, az: 40, el: 26, zoom: 1.02, out: `docs/assets/readme/seedling-exploded-${bg}.png` },
    { id: "seedling_folded", w: 900, h: 1300, bg, az: 20, el: 12, zoom: 1.1, out: `docs/assets/readme/seedling-folded-${bg}.png` },
    { id: "dewdrop_assembly", w: 1600, h: 1000, bg, az: 25, el: 14, zoom: 0.7, out: `docs/assets/readme/dewdrop-assembly-${bg}.png` },
  ]),
];

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
for (const j of jobs) {
  const page = await browser.newPage({ viewport: { width: j.w, height: j.h } });
  page.on("pageerror", (e) => console.error(j.id, e.message));
  const q = new URLSearchParams({ part: j.id, w: j.w, h: j.h, bg: j.bg, ...(j.az != null && { az: j.az }), ...(j.el != null && { el: j.el }), ...(j.zoom && { zoom: j.zoom }), ...(j.tilt && { tilt: j.tilt }) });
  await page.goto(`${base}?${q}`);
  await page.waitForFunction(() => window.__done, null, { timeout: 60000 });
  await mkdir(dirname(join(ROOT, j.out)), { recursive: true });
  await page.locator("canvas").screenshot({ path: join(ROOT, j.out), omitBackground: j.bg === "none" });
  console.log("rendered", j.out);
  await page.close();
}
await browser.close();
server.close();
