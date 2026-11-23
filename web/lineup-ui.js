// Lineup view for the configurator (MIT licence). Reads LINEUP (built from sim/lineup.py by
// sim/build_configurator.py) and computes everything live with maplewing-framework.js.
(function () {
  const F = window.Maplewing, $ = id => document.getElementById(id);
  const ORDER = ["Taproot", "Seedling", "Dewdrop", "Maplewing-1", "Maplewing-1 L2 config", "Maplewing-2", "Maplewing-3"];
  const LABEL = { "Maplewing-1 L2 config": "Maplewing-1 L2" };
  const BLURB = {
    "Taproot": "The affordable control rocket: an Estes Alpha III class, three fins, parachute on motor ejection.",
    "Seedling": "The rotor pathfinder from Phase 0, not one of the five: a BT-50 model with a printed ring tail and a 0.30 m rotor pushed out by the motor's own ejection charge.",
    "Dewdrop": "The water rocket: 2 L PET bottle, printed ring tail, spring-folded rotor released by a mechanical timer.",
    "Maplewing-1": "Single stage, ring tail, rotor with a backup parachute. Level 1 on an H128W reload.",
    "Maplewing-1 L2 config": "The same design scaled to 102 mm for a Level 2 flight on a J350W reload.",
    "Maplewing-2": "Two stages under the FAA Class 2 impulse limit. Both stages are Core-98 modules and each lands on its own.",
  };
  const st = { pick: "Maplewing-2", tail: "fins" };
  try { Object.assign(st, JSON.parse(localStorage.getItem("mw-lineup") || "{}")); } catch (e) {}
  if (!ORDER.includes(st.pick)) st.pick = "Maplewing-2";

  // shared_id used by more than one stage = a module designed once and reused
  const usage = {};
  for (const v of LINEUP.fins) for (const s of v.stages) for (const m of s.modules) if (m.shared_id) (usage[m.shared_id] ||= new Set()).add(v.name + "/" + s.name);

  const picker = $("lu-pick");
  picker.innerHTML = ORDER.map(n => `<button type="button" data-n="${n}" aria-pressed="false">${LABEL[n] || n}</button>`).join("");
  picker.addEventListener("click", e => { const b = e.target.closest("button"); if (b) { st.pick = b.dataset.n; render(); } });
  $("lu-tail").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { st.tail = b.dataset.t; render(); } });

  const fmtAlt = m => m >= 10000 ? (m / 1000).toFixed(1) + " km" : Math.round(m) + " m";
  const motorLine = k => { const m = F.motor(k), d = MOTOR_DATA[k]; return `${k} · ${Math.round(m.I).toLocaleString()} N·s · ${d.type}`; };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function render() {
    picker.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.n === st.pick));
    $("lu-tail").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.t === st.tail));
    const held = st.pick === "Maplewing-3";
    $("lu-held").hidden = !held; $("lu-body").hidden = held;
    $("lu-tailwrap").hidden = held || st.pick !== "Maplewing-2";
    try { localStorage.setItem("mw-lineup", JSON.stringify(st)); } catch (e) {}
    if (held) return;
    const v = LINEUP[st.tail].find(x => x.name === st.pick);
    const c = F.classify(v), f = F.fly(v), errs = F.validate(v);
    $("lu-blurb").textContent = BLURB[v.name];
    $("lu-class").textContent = c.faa_class.replace(/ \(.*/, "");
    $("lu-class-n").textContent = c.faa_class.includes("(") ? c.faa_class.replace(/.*\(|\)/g, "") : "";
    $("lu-cert").textContent = c.cert_level.replace(/ \(.*/, "");
    $("lu-cert-n").textContent = c.total_impulse_Ns ? `${c.total_impulse_Ns.toLocaleString()} N·s total` : "water and air";
    $("lu-apo").textContent = fmtAlt(f.apogee_m);
    $("lu-apo-n").textContent = `top at ${f.t_apogee_s} s · site ${v.site_alt.toLocaleString()} m · vertical upper bound`;
    $("lu-mach").textContent = "Mach " + f.mach_max.toFixed(2);
    $("lu-mach-n").textContent = f.mach_max > 1 ? "supersonic: fins on fast stages by default" : "subsonic";
    const chip = $("lu-rules");
    chip.className = "chip " + (errs.length ? "bad" : "ok");
    chip.textContent = errs.length ? `${errs.length} rule problem${errs.length > 1 ? "s" : ""}` : "Passes all scope rules";
    $("lu-errs").innerHTML = errs.map(e => `<li>${esc(e)}</li>`).join("");
    $("lu-stack").innerHTML = v.stages.map((s, i) => {
      const L = F.sizeLanding(s, v.site_alt), ld = s.landing;
      const ign = i === 0 ? (v.water ? "remote pull-cord release" : "range launch controller")
        : `commercial altimeter airstart, inhibits: ${s.inhibits.join(", ")}`;
      const deploy = { motor_ejection: "motor ejection", commercial_altimeter: "redundant commercial altimeters", mechanical_timer: "mechanical timer" }[ld.deploy];
      const mods = s.modules.map(m => {
        const shared = m.shared_id && usage[m.shared_id] && usage[m.shared_id].size > 1;
        return `<li class="mod${shared ? " shared" : ""}" title="${esc(m.shared_id)}">${esc(m.kind.replace("_", " "))} <span>${m.mass < 1 ? Math.round(m.mass * 1000) + " g" : m.mass.toFixed(1) + " kg"}</span></li>`;
      }).join("");
      return `<li class="stg">
        <div class="stg-h"><small>${v.stages.length > 1 ? "Stage " + (i + 1) : "Single stage"} · ${s.tail === "ring" ? "ring tail" : "fins"} · ⌀${Math.round(s.d * 1000)} mm</small><b>${esc(s.name)}</b>
        <span>${s.motor ? motorLine(s.motor) : `${v.water.psi} psi, ${Math.round(v.water.water_l * 1000)} mL water, proof ${v.water.proof_psi} psi`}</span></div>
        <dl>
          <dt>Lit by</dt><dd>${ign}</dd>
          <dt>Lands on</dt><dd>${ld.primary} ${L.primary_D_m} m at ${L.v_land_ms} m/s${ld.drogue ? ", drogue at apogee" : ""}${ld.backup ? `, backup chute ${L.backup_D_m} m` : ""}</dd>
          <dt>Deployed by</dt><dd>${deploy}</dd>
          <dt>Landing energy</dt><dd>${L.landing_J} J</dd>${i === 0 && f.ejection ? `
          <dt>Ejection</dt><dd>${s.delay_s} s delay: ${ejText(f.ejection, f.t_apogee_s)}</dd>
          <dt>Other delays</dt><dd>${F.ejectionOptions(v).filter(o => o.delay_s !== s.delay_s).map(o => `${o.delay_s} s: ${ejText(o, f.t_apogee_s)}`).join("; ")}</dd>
          <dt>Tilt and wind</dt><dd>${worstText(v)}</dd>
          <dt>Off the rod</dt><dd>${[0.91, 1.22].map(r => `${F.flyTilted(v, 0, 0, r).off_rod_ms} m/s off a ${r} m rod`).join(", ")} (about 15 m/s is a common minimum; check with your club)</dd>` : ""}
        </dl>
        <ul class="mods" aria-label="Modules">${mods}</ul>
      </li>`;
    }).join("");
  }
  function worstText(v) {
    const rows = F.ejectionTable(v), by = {};
    for (const r of rows) by[r.delay_s] = Math.max(by[r.delay_s] || 0, r.speed_ms);
    return "fastest the rocket is moving when recovery deploys, over rod tilts 0–10° and winds 0–5 m/s: " +
      Object.entries(by).map(([d, sp]) => `${d} s delay ${sp} m/s`).join(", ");
  }
  function ejText(e, tApo) {
    const dt = Math.round((e.t_s - tApo) * 10) / 10;
    return `${Math.abs(dt)} s ${dt < 0 ? "before" : "after"} the top, ${e.v_ms >= 0 ? "still climbing" : "already falling"} at ${Math.abs(e.v_ms)} m/s`;
  }
  render();
})();
