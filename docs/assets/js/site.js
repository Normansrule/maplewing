// Maplewing website: fills every section from docs/data/site-data.js (generated from the repo) (MIT).
const D = window.MAPLEWING;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const fmt = (n, d = 0) => Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd = (n) => "$" + fmt(n, 2);
const G = 9.80665;

// ---------- theme toggle (system by default; the choice is remembered on this device only)
(() => {
  const root = document.documentElement, btn = $("[data-theme-toggle]");
  try { const t = localStorage.getItem("mw-theme"); if (t) root.dataset.theme = t; } catch {}
  const isDark = () => root.dataset.theme === "dark" || (!root.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  const label = () => btn && btn.setAttribute("aria-label", isDark() ? "Switch to light theme" : "Switch to dark theme");
  label();
  btn?.addEventListener("click", () => {
    root.dataset.theme = isDark() ? "light" : "dark"; label();
    try { localStorage.setItem("mw-theme", root.dataset.theme); } catch {}
  });
})();

// ---------- headline numbers
const seedling = D.lineup.find((r) => r.name === "Seedling");
const printed = D.cad.parts.filter((p) => !p.paper_only);
const sumBom = (rocket, groups) => D.bom.filter((r) => r.rocket === rocket && r.line_usd != null && (!groups || groups.includes(r.group))).reduce((a, r) => a + r.line_usd, 0);
const firstDay = sumBom("Seedling");
const stats = {
  land: seedling.stages[0].v_land_ms,
  apogee: seedling.apogee_m,
  rockets: D.lineup.filter((r) => !r.name.includes("L2")).length,
  parts: printed.length,
  cost: firstDay,
};
$$("[data-stat]").forEach((el) => {
  const key = el.dataset.stat, v = stats[key], dec = Number(el.dataset.dec || 0);
  const out = (x) => (el.dataset.prefix || "") + fmt(x, dec);
  if (reduce || !("IntersectionObserver" in window)) { el.textContent = out(v); return; }
  el.textContent = out(0);
  const io = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) return; io.disconnect();
    const t0 = performance.now(), dur = 1100;
    const step = (now) => { const u = Math.min(1, (now - t0) / dur), k = 1 - Math.pow(1 - u, 3); el.textContent = out(v * k); if (u < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }, { threshold: 0.6 });
  io.observe(el);
});

// ---------- lineup
(() => {
  const host = $("[data-lineup]"); if (!host) return;
  const maxLog = Math.log10(Math.max(...D.lineup.map((r) => r.apogee_m)));
  const chip = { ready: "Ready to build", paper: "Paper only", sim: "Simulation only" };
  host.innerHTML = D.lineup.map((r, i) => {
    const s0 = r.stages[0];
    const motors = r.stages.map((s) => s.motor).filter(Boolean).join(" + ") || "Water and air, 60 psi";
    const alt = r.apogee_m >= 1000 ? `${fmt(r.apogee_m / 1000, 1)} km` : `${fmt(r.apogee_m)} m`;
    const bar = Math.max(4, (Math.log10(r.apogee_m) / maxLog) * 100);
    const land = r.stages.map((s) => `${s.landing === "rotor" ? `${s.landing_D_m} m rotor` : `${s.landing_D_m} m parachute`}${s.backup_D_m ? ` + ${s.backup_D_m} m backup chute` : ""}`).join("; ");
    return `<article class="rk" style="--i:${i}">
      <header><span class="rk-n">${String(i + 1).padStart(2, "0")}</span><h3>${r.name}</h3><span class="tag tag--${r.status}">${chip[r.status]}</span></header>
      <p>${r.blurb}</p>
      <div class="rk-bar" role="img" aria-label="Simulated apogee ${alt}, on a logarithmic scale"><i style="--w:${bar.toFixed(1)}%"></i></div>
      <dl>
        <div><dt>Apogee (sim)</dt><dd>${alt}</dd></div>
        <div><dt>Top speed</dt><dd>Mach ${fmt(r.mach, 2)}</dd></div>
        <div><dt>Motor</dt><dd>${motors}</dd></div>
        <div><dt>FAA · cert</dt><dd>${r.faa.replace(/ \(.*\)/, "")} · ${r.cert === "none" ? "none" : r.cert}</dd></div>
        <div><dt>Lands on</dt><dd>${land}</dd></div>
        <div><dt>Landing speed</dt><dd>${fmt(s0.v_land_ms, 1)} m/s</dd></div>
      </dl>
      <footer>${r.status_note}</footer>
    </article>`;
  }).join("");
})();

// ---------- parts gallery
(() => {
  const host = $("[data-parts]"); if (!host) return;
  const groups = ["Seedling", "Dewdrop", "Maplewing-1"];
  host.innerHTML = groups.map((g) => {
    const ps = D.cad.parts.filter((p) => p.rocket === g);
    return `<div class="pg"><h3>${g}${g === "Maplewing-1" ? ` <span class="tag tag--paper">Paper only</span>` : ""}</h3><ul>${ps.map((p) => {
      const over = p.mass_g > p.budget_g;
      return `<li><button class="part" type="button" data-part="${p.id}" aria-haspopup="dialog">
        <img src="${p.img}" alt="" width="600" height="600" loading="lazy" decoding="async">
        <span class="part-t">${p.title}${p.qty > 1 ? ` <small>× ${p.qty}</small>` : ""}</span>
        <span class="part-m">${p.material === "balsa" ? "Balsa" : "PETG"} · ${p.mass_g} g <span class="${over ? "over" : "under"}">${over ? "over" : "within"} ${p.budget_g} g budget</span></span>
      </button><a class="part-dl" href="${p.stl}" download="${p.id}.stl" aria-label="Download ${g} ${p.title} STL">STL</a></li>`;
    }).join("")}</ul></div>`;
  }).join("");
})();

// ---------- costs
(() => {
  const host = $("[data-bom]"), tabs = $("[data-bom-tabs]"); if (!host || !tabs) return;
  const rockets = [...new Set(D.bom.map((r) => r.rocket))];
  const label = { printed: "Printed", airframe: "Airframe", "per-flight": "Per flight", ground: "Ground support" };
  tabs.innerHTML = rockets.map((r, i) => `<button type="button" role="tab" id="bt-${i}" aria-controls="bom-panel" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}">${r}</button>`).join("");
  const draw = (rocket) => {
    const rows = D.bom.filter((r) => r.rocket === rocket);
    const total = rows.reduce((a, r) => a + (r.line_usd || 0), 0);
    const unpriced = rows.filter((r) => r.line_usd == null).length;
    const groups = Object.keys(label).filter((g) => rows.some((r) => r.group === g));
    host.innerHTML = `<div class="tbl"><table>
      <caption class="sr-only">${rocket} parts and listed prices</caption>
      <thead><tr><th scope="col">Part</th><th scope="col" class="n">Qty</th><th scope="col" class="n">Price</th><th scope="col">Status</th><th scope="col">Source</th></tr></thead>
      ${groups.map((g) => `<tbody><tr class="grp"><th scope="rowgroup" colspan="5">${label[g]} <span>${usd(rows.filter((r) => r.group === g).reduce((a, r) => a + (r.line_usd || 0), 0))}</span></th></tr>
        ${rows.filter((r) => r.group === g).map((r) => `<tr><td><b>${r.id}</b> ${r.item}${r.notes ? `<small>${r.notes}</small>` : ""}</td><td class="n">${r.qty}</td>
        <td class="n">${r.line_usd == null ? "—" : usd(r.line_usd)}</td><td><span class="st st--${r.status.replace(/\s/g, "-")}">${r.status}</span></td>
        <td>${r.source_url ? `<a href="${r.source_url}" rel="noopener">${r.source || "link"}</a>` : (r.source || "")}${r.checked ? `<small>${r.checked}</small>` : ""}</td></tr>`).join("")}</tbody>`).join("")}
      <tfoot><tr><th scope="row">Total listed</th><td></td><td class="n">${usd(total)}</td><td colspan="2">${unpriced ? `${unpriced === 1 ? "1 item still needs a quote" : `${unpriced} items still need a quote`}` : "every line priced"}</td></tr></tfoot>
    </table></div>`;
  };
  tabs.addEventListener("click", (e) => {
    const b = e.target.closest("[role=tab]"); if (!b) return;
    $$("[role=tab]", tabs).forEach((x) => { x.setAttribute("aria-selected", String(x === b)); x.tabIndex = x === b ? 0 : -1; });
    $("#bom-panel").setAttribute("aria-labelledby", b.id);
    draw(b.textContent);
  });
  tabs.addEventListener("keydown", (e) => {
    const all = $$("[role=tab]", tabs), i = all.indexOf(document.activeElement);
    if (i < 0 || !["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const j = e.key === "Home" ? 0 : e.key === "End" ? all.length - 1 : (i + (e.key === "ArrowRight" ? 1 : -1) + all.length) % all.length;
    all[j].focus(); all[j].click();
  });
  $("#bom-panel").setAttribute("aria-labelledby", "bt-0");
  draw(rockets[0]);
  const csv = $("[data-bom-csv]");
  if (csv) csv.textContent = `Seedling, first day: ${usd(firstDay)} listed (airframe ${usd(sumBom("Seedling", ["printed", "airframe"]))}, motors and wadding ${usd(sumBom("Seedling", ["per-flight"]))}, pad ${usd(sumBom("Seedling", ["ground"]))}).`;
})();

// ---------- why it spins: descent speed for a rotor and a parachute of the same diameter
(() => {
  const host = $("[data-spin]"); if (!host) return;
  const m = $("#spin-m", host), d = $("#spin-d", host);
  const rho = 1.225 * Math.pow((288.15 - 0.0065 * 1300) / 288.15, 4.2559); // 1,300 m field, as in the sim
  const rotor = $("[data-rotor]", host), outR = $("[data-v-rotor]", host), outC = $("[data-v-chute]", host);
  const outM = $("output[for=spin-m]", host), outD = $("output[for=spin-d]", host), verdict = $("[data-verdict]", host);
  const barR = $("[data-bar-rotor]", host), barC = $("[data-bar-chute]", host);
  const R = D.rotor;
  const upd = () => {
    const mass = Number(m.value) / 1000, dia = Number(d.value) / 100, A = Math.PI * dia * dia / 4;
    const vr = Math.sqrt((2 * mass * G) / (rho * R.C_rotor * A)), vc = Math.sqrt((2 * mass * G) / (rho * R.C_chute * A));
    outM.textContent = `${m.value} g`; outD.textContent = `${d.value} cm`;
    outR.textContent = `${fmt(vr, 1)} m/s`; outC.textContent = `${fmt(vc, 1)} m/s`;
    const scale = 14;
    barR.style.setProperty("--w", `${Math.min(100, (vr / scale) * 100)}%`); barC.style.setProperty("--w", `${Math.min(100, (vc / scale) * 100)}%`);
    const need = Math.sqrt((8 * mass * G) / (Math.PI * rho * R.C_rotor * R.v_target_ms ** 2)) * 100;
    verdict.textContent = vr <= R.v_target_ms
      ? `Lands at ${fmt(vr, 1)} m/s, under the ${R.v_target_ms} m/s target.`
      : `Too fast at ${fmt(vr, 1)} m/s. A ${fmt(need, 0)} cm rotor would land at ${R.v_target_ms} m/s.`;
    // The drawn disc spins faster as descent speed rises (tip speed scales with descent speed).
    const rps = Math.min(6, (vr * 4.2) / (Math.PI * dia));
    rotor.style.setProperty("--dur", `${(1 / rps).toFixed(3)}s`);
  };
  m.addEventListener("input", upd); d.addEventListener("input", upd); upd();
})();

// ---------- equations (KaTeX, vendored)
if (window.katex) $$("[data-tex]").forEach((el) => window.katex.render(el.dataset.tex, el, { displayMode: el.tagName !== "SPAN", throwOnError: false }));

// ---------- keyboard access: a box that scrolls sideways (wide equations, code, tables) must take focus
function scrollFocus() {
  $$(".eqs article > div, .eq, .tbl, pre").forEach((el) => {
    const wide = el.scrollWidth > el.clientWidth + 1;
    el.toggleAttribute("data-scrolls", wide);
    if (wide) {
      el.tabIndex = 0; el.setAttribute("role", "region");
      const name = el.matches(".tbl") ? "Parts list" : el.matches("pre") ? "Commands" : el.closest("article")?.querySelector("h3")?.textContent || "Equation";
      el.setAttribute("aria-label", `${name}, scrolls sideways`);
    } else if (el.getAttribute("role") === "region") {
      el.tabIndex = -1; el.setAttribute("role", "presentation");
    }
  });
}
scrollFocus(); document.fonts?.ready.then(scrollFocus);
if ("ResizeObserver" in window) { const ro = new ResizeObserver(scrollFocus); $$(".eqs article > div, .eq, .tbl, pre").forEach((el) => ro.observe(el)); }

// ---------- reveal on scroll (opacity only; off for reduced motion)
if (!reduce && "IntersectionObserver" in window) {
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -10% 0px" });
  $$(".reveal").forEach((el) => io.observe(el));
} else $$(".reveal").forEach((el) => el.classList.add("in"));

// ---------- downloads: point the desktop buttons at the newest GitHub release when there is one
(async () => {
  const host = $("[data-release]"); if (!host) return;
  try {
    const r = await fetch("https://api.github.com/repos/Normansrule/maplewing/releases/latest", { headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) return;
    const rel = await r.json();
    const pick = (re) => rel.assets.find((a) => re.test(a.name));
    const map = { win: pick(/\.msi$|setup\.exe$/i), mac: pick(/\.dmg$/i), linux: pick(/\.AppImage$/i) || pick(/\.deb$/i) };
    for (const [k, a] of Object.entries(map)) { const el = $(`[data-dl=${k}]`); if (a && el) { el.href = a.browser_download_url; el.querySelector("small").textContent = `${rel.tag_name} · ${a.name.split(".").pop()}`; } }
  } catch {}
})();
