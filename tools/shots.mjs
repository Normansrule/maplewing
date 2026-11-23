#!/usr/bin/env node
// README screenshots and the hero animation, taken from the real site and app in headless Chromium (MIT).
//   docs/assets/readme/{site,app,phone}-{light,dark}.png, og.png, hero-{light,dark}.webp
// Usage: node tools/shots.mjs   (needs Playwright with Chromium and ffmpeg; `make shots`)
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, mkdir, mkdtemp, rm } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { extname, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const DOCS = join(dirname(fileURLToPath(import.meta.url)), "..", "docs");
const OUT = join(DOCS, "assets", "readme");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".stl": "model/stl", ".json": "application/json", ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp" };
const server = createServer(async (req, res) => {
  try {
    let p = join(DOCS, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!p.startsWith(DOCS)) throw new Error("outside");
    if (p.endsWith("/")) p += "index.html";
    res.writeHead(200, { "content-type": TYPES[extname(p)] || "application/octet-stream" }).end(await readFile(p));
  } catch { res.writeHead(404).end(); }
}).listen(0);
const base = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
await mkdir(OUT, { recursive: true });

async function open(path, { w, h, scheme, scale = 2, mobile = false }) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: scale, colorScheme: scheme, isMobile: mobile, hasTouch: mobile });
  // GitHub's releases API is not reachable from a local server; answer it so the page stays quiet.
  await ctx.route("https://api.github.com/**", (r) => r.fulfill({ status: 404, body: "{}" }));
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.error(path, e.message));
  await page.goto(base + path, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  return { page, ctx };
}

async function heroAt(page, seconds) {
  await page.waitForFunction(() => window.__hero);
  await page.evaluate(() => window.__hero.reset());
  await page.evaluate((n) => window.__hero.step(n), Math.round(seconds * 30));
  await page.waitForTimeout(200);
}

for (const scheme of ["light", "dark"]) {
  // Website, first screen, mid-descent with the rotor open.
  let { page, ctx } = await open("", { w: 1440, h: 900, scheme });
  await heroAt(page, 11.5);
  await page.screenshot({ path: join(OUT, `site-${scheme}.png`) });
  console.log("shot", `site-${scheme}.png`);
  if (scheme === "light") { // social card: 1200 x 630, from a 1440 x 756 view so the layout stays desktop
    await page.setViewportSize({ width: 1440, height: 756 });
    await heroAt(page, 11.5);
    const tmp = join(OUT, "og-full.png");
    await page.screenshot({ path: tmp, scale: "css" });
    execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", tmp, "-vf", "scale=1200:630:flags=lanczos", join(OUT, "og.png")]);
    await rm(tmp);
    console.log("shot og.png");
  }
  await ctx.close();

  // Configurator app.
  ({ page, ctx } = await open("app/", { w: 1440, h: 900, scheme }));
  await page.waitForTimeout(800);
  await page.screenshot({ path: join(OUT, `app-${scheme}.png`) });
  console.log("shot", `app-${scheme}.png`);
  await ctx.close();

  // Phone.
  ({ page, ctx } = await open("", { w: 390, h: 844, scheme, scale: 3, mobile: true }));
  await heroAt(page, 11.5);
  await page.screenshot({ path: join(OUT, `phone-${scheme}.png`) });
  console.log("shot", `phone-${scheme}.png`);
  await ctx.close();

  // Hero animation: one full flight, stepped deterministically so every frame is the same on every run.
  ({ page, ctx } = await open("", { w: 960, h: 540, scheme, scale: 1 }));
  await page.waitForFunction(() => window.__hero);
  await page.evaluate(() => window.__hero.reset());
  const dir = await mkdtemp(join(tmpdir(), "mw-hero-"));
  const fps = 15, seconds = 16.5, hero = page.locator("[data-hero]");
  for (let i = 0; i < fps * seconds; i++) {
    await page.evaluate((n) => window.__hero.step(n), 30 / fps);
    await hero.screenshot({ path: join(dir, `f${String(i).padStart(4, "0")}.png`) });
  }
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-framerate", String(fps), "-i", join(dir, "f%04d.png"),
    "-vf", "scale=800:-2:flags=lanczos", "-c:v", "libwebp", "-lossless", "0", "-q:v", "72", "-compression_level", "6", "-loop", "0",
    join(OUT, `hero-${scheme}.webp`)]);
  await rm(dir, { recursive: true });
  console.log("animation", `hero-${scheme}.webp`);
  await ctx.close();
}
await browser.close();
server.close();
