// Maplewing shared framework, browser/Node mirror of sim/maplewing_framework.py (MIT licence).
// Same types, same scope-rule checks, same classification, same multi-stage flight and landing
// sizing. sim/test_framework_agree.py runs this under Node and compares it with Python.

/** @typedef {{kind:string, mass:number, shared_id?:string, reusable?:boolean, metal?:boolean}} Module
 *  kind: nose | avbay | rotor_bay | chute_bay | ring_tail | fins | interstage | motor_mount | body | bottle */
/** @typedef {{primary:'rotor'|'parachute', backup:'parachute'|null,
 *   deploy:'motor_ejection'|'commercial_altimeter'|'mechanical_timer',
 *   redundant_altimeters?:boolean, drogue?:boolean, primary_d?:number, backup_d?:number}} Landing */
/** @typedef {{name:string, d:number, cd:number, tail:'ring'|'fins', modules:Module[], landing:Landing,
 *   motor:string|null, ignition:'ground'|'commercial_altimeter', inhibits:string[], delay_s:number|null}} Stage */
/** @typedef {{name:string, tier:string, stages:Stage[], site_alt:number, staging_delay_s:number,
 *   water:null|{psi:number, water_l:number, bottle:string, remote_release:boolean}}} Vehicle */

(function (root) {
  // In Node these come from require(); in the browser from motors-data.js (var MOTOR_DATA) and
  // maplewing-core.js (function declarations), loaded as classic scripts before this one.
  const NODE = typeof module !== 'undefined' && typeof require !== 'undefined';
  const MOTOR_DATA = NODE ? require('./motors-data.js') : root.MOTOR_DATA;
  const core = NODE ? require('./maplewing-core.js') : root;

  const R = {
    FAA_C1_MAX_PROP_KG: 0.125, FAA_C1_MAX_MASS_KG: 1.5, FAA_C2_MAX_IMPULSE: 40960,
    FAA_AMATEUR_MAX_IMPULSE: 889600, NFPA: { prop_kg: 0.0625, impulse: 160, avg_thrust: 80 },
    LANDING_TARGET_MS: 6.5, WATER_MAX_PSI: 60,
    FORBIDDEN: new Set(['guidance', 'tvc', 'canard', 'servo', 'active_rotor', 'steerable_fin', 'pyro_diy']),
    ROTOR_C_EFF: 1.08, CHUTE_CD: 1.5,
  };
  const G0 = 9.80665, RAIR = 287.053, GAM = 1.4, RE = 6.371e6;

  const motors = {};
  function motor(k) { if (!motors[k]) motors[k] = core.prepMotor(JSON.parse(JSON.stringify(MOTOR_DATA[k]))); return motors[k]; }
  const impulse = k => motor(k).I;
  function letter(I) { let hi = 2.5; for (const L of 'ABCDEFGHIJKLMNOP') { if (I <= hi + 1e-9) return L; hi *= 2; } return '?'; }
  function isModelMotor(k) { const m = motor(k), I = m.I; return m.mp <= R.NFPA.prop_kg + 1e-6 && I <= R.NFPA.impulse && I / m.tb <= R.NFPA.avg_thrust; }
  const dry = s => s.modules.reduce((a, m) => a + m.mass, 0);
  const liftoffMass = v => v.stages.reduce((a, s) => a + dry(s) + (s.motor ? motor(s.motor).mt : 0), 0);

  // 1976 US Standard Atmosphere, same table as sim/high_altitude.py
  const LAYERS = [[0, 288.15, -6.5], [11, 216.65, 0], [20, 216.65, 1], [32, 228.65, 2.8], [47, 270.65, 0], [51, 270.65, -2.8], [71, 214.65, -2], [84.852, 186.87, 0]];
  const PB = [101325];
  for (let i = 0; i < LAYERS.length - 1; i++) {
    const [h0, T0, L] = LAYERS[i], dh = (LAYERS[i + 1][0] - h0) * 1000;
    PB.push(L === 0 ? PB[i] * Math.exp(-G0 * dh / (RAIR * T0)) : PB[i] * Math.pow((T0 + L / 1000 * dh) / T0, -G0 / (RAIR * L / 1000)));
  }
  function atmos(z) {
    if (z > 86000) return [0, 275];
    const h = RE * z / (RE + z) / 1000; let i = 0;
    for (let k = 0; k < LAYERS.length; k++) if (LAYERS[k][0] <= h) i = k;
    const [h0, T0, L] = LAYERS[i], T = T0 + L * (h - h0);
    const P = PB[i] * (L === 0 ? Math.exp(-G0 * (h - h0) * 1000 / (RAIR * T0)) : Math.pow(T / T0, -G0 / (RAIR * L / 1000)));
    return [P / (RAIR * T), Math.sqrt(GAM * RAIR * T)];
  }
  const MACH_CD = [[0, 1], [0.8, 1], [1.05, 1.65], [1.3, 1.55], [2, 1.15], [3, 0.95], [5, 0.8], [8, 0.75]];
  function cdMult(M) { for (let i = 0; i < MACH_CD.length - 1; i++) { const [m0, c0] = MACH_CD[i], [m1, c1] = MACH_CD[i + 1]; if (M <= m1) return c0 + (c1 - c0) * (M - m0) / (m1 - m0); } return MACH_CD[MACH_CD.length - 1][1]; }

  function classify(v) {
    const keys = v.stages.filter(s => s.motor).map(s => s.motor);
    if (!keys.length) return { faa_class: 'not an FAA amateur rocket (water/air)', cert_level: 'none', total_impulse_Ns: 0 };
    const I = keys.reduce((a, k) => a + impulse(k), 0), prop = keys.reduce((a, k) => a + motor(k).mp, 0);
    const metal = v.stages.some(s => s.modules.some(m => m.metal));
    let faa;
    if (prop <= R.FAA_C1_MAX_PROP_KG && liftoffMass(v) <= R.FAA_C1_MAX_MASS_KG && !metal) faa = 'Class 1 (model rocket)';
    else if (I <= R.FAA_C2_MAX_IMPULSE) faa = 'Class 2 (high-power)';
    else if (I <= R.FAA_AMATEUR_MAX_IMPULSE) faa = 'Class 3 (advanced high-power)';
    else faa = 'not amateur: FAA launch licence';
    const worst = keys.reduce((a, k) => impulse(k) > impulse(a) ? k : a), L = letter(impulse(worst));
    let cert;
    if (keys.every(isModelMotor) && liftoffMass(v) <= R.FAA_C1_MAX_MASS_KG) cert = L === 'G' ? 'none (G and up: adult purchase)' : 'none';
    else cert = { H: 'Level 1', I: 'Level 1', J: 'Level 2', K: 'Level 2', L: 'Level 2', M: 'Level 3', N: 'Level 3', O: 'Level 3' }[L] || 'Level 1 (HPR by mass/thrust)';
    return { faa_class: faa, cert_level: cert, total_impulse_Ns: Math.round(I) };
  }

  function validate(v) {
    const bad = v.stages.filter(s => s.motor != null && (!MOTOR_DATA[s.motor] || !MOTOR_DATA[s.motor].cert_org))
      .map(s => `${v.name} / ${s.name}: motor ${s.motor} is not a certified commercial motor in motors.json`);
    if (bad.length) return bad;  // cannot classify or fly an uncertified motor
    const errs = [], hpr = classify(v).cert_level.startsWith('Level');
    v.stages.forEach((s, i) => {
      const tag = `${v.name} / ${s.name}`;
      for (const m of s.modules) if (R.FORBIDDEN.has(m.kind)) errs.push(`${tag}: module '${m.kind}' is active control or DIY pyro (out of scope)`);
      if (!s.landing || !['rotor', 'parachute'].includes(s.landing.primary)) errs.push(`${tag}: every stage needs its own passive landing system`);
      if (s.motor != null) { if (!MOTOR_DATA[s.motor] || !MOTOR_DATA[s.motor].cert_org) errs.push(`${tag}: motor ${s.motor} is not a certified commercial motor in motors.json`); }
      else if (!v.water) errs.push(`${tag}: no motor and not a water rocket`);
      if (i > 0) {
        if (s.ignition !== 'commercial_altimeter') errs.push(`${tag}: upper stage must be lit by a commercial altimeter (not timer-only, motor ejection or DIY)`);
        const inh = new Set(s.inhibits || []);
        if (!['altitude', 'tilt', 'time'].some(x => inh.has(x)) || !inh.has('altitude')) errs.push(`${tag}: airstart needs an altitude inhibit plus tilt or time window`);
      } else if (s.ignition !== 'ground') errs.push(`${tag}: first stage is lit on the ground by the range's launch controller`);
      if (hpr) {
        if (s.landing.deploy !== 'commercial_altimeter' || !s.landing.redundant_altimeters) errs.push(`${tag}: HPR stages deploy with redundant commercial altimeters`);
        if (s.landing.primary === 'rotor' && s.landing.backup !== 'parachute') errs.push(`${tag}: rotor stages keep a backup parachute`);
      }
      if (s.landing && s.landing.deploy === 'motor_ejection' && s.motor != null) {
        const sold = MOTOR_DATA[s.motor].delays_s || [];
        if (!sold.includes(s.delay_s)) errs.push(`${tag}: motor ejection needs a delay the ${s.motor} is sold with (${sold.join(', ') || 'none listed'} s)`);
      }
    });
    if (v.water) {
      const w = v.water;
      if (w.psi > R.WATER_MAX_PSI) errs.push(`${v.name}: ${w.psi} psi > ${R.WATER_MAX_PSI} psi limit`);
      if (w.bottle !== 'PET') errs.push(`${v.name}: rated PET bottles only`);
      if (!w.remote_release) errs.push(`${v.name}: remote release required`);
    }
    return errs;
  }

  function rhoISA(h) { const T = 288.15 - 0.0065 * h; return 1.225 * Math.pow(T / 288.15, 4.2559); }

  // Water rocket, a line-by-line port of phase0_compare.water_rocket (Euler, dt 1e-4).
  function water(psi, Vw, dryM, dBody, cd, gamma = 1.4, dt = 1e-4) {
    const Pa = 101325, P0 = Pa + psi * 6894.76, Vb = 0.002, dn = 0.0217, An = Math.PI * dn * dn / 4, A = Math.PI * dBody * dBody / 4, Va0 = Vb - Vw;
    let mw = Vw * 1000; let mAir = P0 / (287 * 293) * Va0; let t = 0, h = 0, v = 0, vmax = 0;
    while (mw > 0) {
      const Va = Vb - mw / 1000, P = P0 * Math.pow(Va0 / Va, gamma); if (P <= Pa) break;
      const ve = Math.sqrt(2 * (P - Pa) / 1000), mdot = 1000 * An * ve, F = mdot * ve, m = dryM + mw + mAir;
      const a = (F - 0.5 * rhoISA(h) * v * Math.abs(v) * cd * A) / m - G0;
      v += a * dt; h += v * dt; t += dt; mw -= mdot * dt; vmax = Math.max(vmax, v);
    }
    let P = P0 * Math.pow(Va0 / Vb, gamma), T = 293 * Math.pow(P / P0, (gamma - 1) / gamma);
    while (P > Pa * 1.01) {
      const rhoA = mAir / Vb; let mdot, F;
      if (P / Pa > 1.893) {
        mdot = An * P * Math.sqrt(gamma / (287 * T)) * Math.pow(2 / (gamma + 1), (gamma + 1) / (2 * (gamma - 1)));
        const Te = T * 2 / (gamma + 1), ve = Math.sqrt(gamma * 287 * Te), Pe = P * Math.pow(2 / (gamma + 1), gamma / (gamma - 1));
        F = mdot * ve + (Pe - Pa) * An;
      } else { const ve = Math.sqrt(2 * (P - Pa) / rhoA); mdot = rhoA * An * ve; F = mdot * ve; }
      const m = dryM + mAir, a = (F - 0.5 * rhoISA(h) * v * Math.abs(v) * cd * A) / m - G0;
      v += a * dt; h += v * dt; t += dt; mAir -= mdot * dt;
      P = P * Math.pow(mAir / (mAir + mdot * dt), gamma); T = T * Math.pow(mAir / (mAir + mdot * dt), gamma - 1); vmax = Math.max(vmax, v);
    }
    while (v > 0) { const a = -G0 - 0.5 * rhoISA(h) * v * Math.abs(v) * cd * A / dryM; v += a * dt; h += v * dt; t += dt; }
    return { apogee_m: Math.round(h * 10) / 10, vmax_ms: Math.round(vmax * 10) / 10, mach_max: Math.round(vmax / 340 * 100) / 100, t_apogee_s: Math.round(t * 10) / 10 };
  }

  // Vertical multi-stage flight, identical integrator to maplewing_framework.fly.
  function fly(v, dt = 0.005) {
    if (v.water) { const s = v.stages[0]; return water(v.water.psi, v.water.water_l / 1000, dry(s), s.d, s.cd); }
    const st = v.stages.map(s => ({ m: motor(s.motor), dry: dry(s), d: s.d, cd: s.cd }));
    let t = 0, h = 0, vel = 0, k = 0, tIgn = 0, vmax = 0, Mmax = 0;
    const s0 = v.stages[0];
    const ejT = (st.length === 1 && s0.landing && s0.landing.deploy === 'motor_ejection' && s0.delay_s != null) ? st[0].m.tb + s0.delay_s : null;
    let ej = null, apo = null;
    while (true) {
      const live = st.slice(k), m0 = live[0].m, tm = t - tIgn;
      const m = live.reduce((a, s) => a + s.dry, 0) + core.motorMass(m0, tm) + live.slice(1).reduce((a, s) => a + s.m.mt, 0);
      const F = core.thrust(m0, tm), [rho, a] = atmos(v.site_alt + h), M = Math.abs(vel) / a;
      const d = Math.max(...live.map(s => s.d)), q = 0.5 * rho * vel * vel;
      const D = q * live[0].cd * cdMult(M) * Math.PI * d * d / 4 * (vel >= 0 ? 1 : -1);
      const g = G0 * (RE / (RE + v.site_alt + h)) ** 2;
      let acc = (F - D) / m - g; if (h <= 0 && acc < 0) acc = 0;
      vel += acc * dt; h += vel * dt; t += dt;
      vmax = Math.max(vmax, vel); Mmax = Math.max(Mmax, M);
      if (live.length > 1 && tm > m0.tb + v.staging_delay_s) { k++; tIgn = t; }
      if (ejT != null && ej == null && tm >= ejT) ej = { t_s: Math.round(t * 10) / 10, alt_m: Math.round(h), v_ms: Math.round(vel * 10) / 10 };
      if (apo == null && st.length - k === 1 && tm > m0.tb && vel < 0) apo = [h, t];
      if (apo != null && (ejT == null || ej != null)) break;
    }
    [h, t] = apo;
    const out = { apogee_m: Math.round(h), vmax_ms: Math.round(vmax), mach_max: Math.round(Mmax * 100) / 100, t_apogee_s: Math.round(t * 10) / 10 };
    if (ej) out.ejection = ej;
    return out;
  }

  // Fly a motor-ejection rocket with every delay its motor is sold with (mirror of ejection_options).
  function ejectionOptions(v) {
    const s = v.stages[0];
    return (MOTOR_DATA[s.motor].delays_s || []).map(d => ({ delay_s: d, ...fly({ ...v, stages: [{ ...s, delay_s: d }] }).ejection }));
  }

  function sizeLanding(s, siteAlt) {
    const m = dry(s) + (s.motor ? motor(s.motor).mt - motor(s.motor).mp : 0), rho = rhoISA(siteAlt), L = s.landing;
    const Dfor = c => Math.sqrt(4 * 2 * m * G0 / (rho * c * R.LANDING_TARGET_MS ** 2) / Math.PI);
    const c = L.primary === 'rotor' ? R.ROTOR_C_EFF : R.CHUTE_CD, Dp = L.primary_d || Dfor(c);
    const vp = Math.sqrt(2 * m * G0 / (rho * c * Math.PI * Dp * Dp / 4));
    const out = { stage: s.name, primary_D_m: Math.round(Dp * 100) / 100, v_land_ms: Math.round(vp * 100) / 100, landing_J: Math.round(5 * m * vp * vp) / 10 };
    if (L.backup) out.backup_D_m = Math.round((L.backup_d || Dfor(R.CHUTE_CD)) * 100) / 100;
    return out;
  }

  // 2-D flight off a tilted rod in a steady wind (mirror of fly_tilted). Single-stage motor rockets only.
  function flyTilted(v, angleDeg = 0, windMs = 0, railM = 0.91, dt = 0.005) {
    const s = v.stages[0], mo = motor(s.motor), d = dry(s);
    const th = angleDeg * Math.PI / 180, ux = Math.sin(th), uy = Math.cos(th), A = Math.PI * s.d * s.d / 4;
    const ejT = (s.landing && s.landing.deploy === 'motor_ejection' && s.delay_s != null) ? mo.tb + s.delay_s : null;
    let t = 0, x = 0, h = 0, vx = 0, vy = 0, onRail = true, apo = null, ej = null, offRail = null;
    while (true) {
      const m = d + core.motorMass(mo, t), F = core.thrust(mo, t), [rho, a] = atmos(v.site_alt + h);
      const rx = vx - windMs, ry = vy, sp = Math.hypot(rx, ry);
      const [dx, dy] = (onRail || sp === 0) ? [ux, uy] : [rx / sp, ry / sp];
      const Dm = 0.5 * rho * sp * sp * s.cd * cdMult(sp / a) * A;
      let fx = F * dx, fy = F * dy;
      if (sp > 0) { fx -= Dm * rx / sp; fy -= Dm * ry / sp; }
      const g = G0 * (RE / (RE + v.site_alt + h)) ** 2;
      let ax = fx / m, ay = fy / m - g;
      if (onRail) { let al = ax * ux + ay * uy; if (x * ux + h * uy <= 0) al = Math.max(al, 0); ax = al * ux; ay = al * uy; }
      vx += ax * dt; vy += ay * dt; x += vx * dt; h += vy * dt; t += dt;
      if (onRail && x * ux + h * uy >= railM) { onRail = false; offRail = Math.round(Math.hypot(vx, vy) * 10) / 10; }
      if (ejT != null && ej == null && t >= ejT) ej = { t_s: Math.round(t * 10) / 10, alt_m: Math.round(h), v_ms: Math.round(vy * 10) / 10, speed_ms: Math.round(Math.hypot(vx, vy) * 10) / 10 };
      if (apo == null && t > mo.tb && vy < 0) apo = { apogee_m: Math.round(h), t_apogee_s: Math.round(t * 10) / 10, x_at_apogee_m: Math.round(x) };
      if (apo != null && (ejT == null || ej != null)) break;
    }
    const out = { ...apo, angle_deg: angleDeg, wind_ms: windMs, off_rod_ms: offRail };
    if (ej) out.ejection = ej;
    return out;
  }

  const LAUNCH_CASES = [[0, 0], [5, 0], [10, 0], [0, 3], [0, 5], [5, 5]];
  function ejectionTable(v, cases = LAUNCH_CASES) {
    const s = v.stages[0], rows = [];
    for (const dl of MOTOR_DATA[s.motor].delays_s || []) for (const [ang, w] of cases) {
      const f = flyTilted({ ...v, stages: [{ ...s, delay_s: dl }] }, ang, w), e = f.ejection;
      rows.push({ delay_s: dl, angle_deg: ang, wind_ms: w, t_apogee_s: f.t_apogee_s, apogee_m: f.apogee_m,
                  eject_vs_top_s: Math.round((e.t_s - f.t_apogee_s) * 10) / 10, speed_ms: e.speed_ms, v_ms: e.v_ms });
    }
    return rows;
  }

  const api = { R, motor, letter, classify, validate, fly, ejectionOptions, flyTilted, ejectionTable, atmos, cdMult, sizeLanding, dry, liftoffMass };
  if (typeof module !== 'undefined') module.exports = api; else root.Maplewing = api;
})(typeof window !== 'undefined' ? window : globalThis);
