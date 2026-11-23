// Hero: a maple seed spins down, becomes Seedling, launches, unfolds its rotor at apogee,
// spins softly back to the pad and launches again. Built from the real CAD parts (MIT).
// Respects prefers-reduced-motion (one still frame), pauses off-screen and has a pause button.
import * as THREE from "three";
import { buildSeedling, buildSamara, materials, studio } from "./rocket3d.js";

const host = document.querySelector("[data-hero]");
const canvas = host?.querySelector("canvas");
const caption = host?.querySelector("[data-caption]");
const counter = host?.querySelector("[data-flight]");
const pauseBtn = host?.querySelector("[data-pause]");
const reduce = matchMedia("(prefers-reduced-motion: reduce)");

const CAPTIONS = {
  seed: ["Samara", "A maple seed spins as it falls. Nothing to steer, nothing to break."],
  morph: ["Seedling", "Same idea, rocket-sized: a ring tail and a folded three-blade rotor."],
  launch: ["Boost", "Certified C6-5 motor. 263 m in the sim, Mach 0.22."],
  apogee: ["Apogee", "The motor's own ejection charge frees the rotor. Pitch is fixed at 6°."],
  descent: ["Spin-down", "Autorotation: 4.4 m/s, about the same as a parachute. Measured next."],
  land: ["Landed", "Fold the blades, repack, fly again. Target: 10 flights per airframe."],
};

const ease = {
  smooth: (u) => u * u * (3 - 2 * u),
  outBack: (u) => { const c = 1.70158, d = u - 1; return 1 + (c + 1) * d * d * d + c * d * d; },
  inOut: (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2),
};

if (host && canvas) init().catch((e) => { console.warn("hero 3D unavailable:", e); host.classList.add("hero--static"); });

async function init() {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 400);
  const dark = matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light";
  const M = materials(dark);
  const lights = await studio(renderer, scene);

  // Ground: shadow catcher, a soft disc and the pad with a true-scale 1.22 m rod (rocket is 0.5 m).
  const S = 0.01; // 1 world unit = 100 mm
  const ground = new THREE.Mesh(new THREE.CircleGeometry(60, 64), new THREE.ShadowMaterial({ opacity: dark ? 0.5 : 0.18 }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  const grid = new THREE.PolarGridHelper(18, 12, 6, 64, dark ? 0x3a4350 : 0xb9c8d6, dark ? 0x262d36 : 0xd6e1ea);
  grid.material.transparent = true; grid.material.opacity = 0.55; grid.position.y = 0.002; scene.add(grid);
  const pad = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.05, 0.12, 48), M.carbon); pad.position.y = 0.06; pad.receiveShadow = true; pad.castShadow = true;
  const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 12.2, 8), new THREE.MeshStandardMaterial({ color: 0x9aa3ad, metalness: 0.9, roughness: 0.3 }));
  rod.position.set(0.32, 6.1, 0); rod.castShadow = true;
  scene.add(pad, rod);

  const rocket = await buildSeedling("", M);
  rocket.scale.setScalar(S);
  const { blades, flame, setNose } = rocket.userData;
  scene.add(rocket);
  const seed = buildSamara(M); seed.scale.setScalar(S * 2.2); scene.add(seed);

  // Smoke: a pool of soft sprites.
  const puffTex = (() => {
    const c = document.createElement("canvas"); c.width = c.height = 64; const g = c.getContext("2d");
    const r = g.createRadialGradient(32, 32, 0, 32, 32, 32); r.addColorStop(0, "rgba(255,255,255,0.9)"); r.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = r; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c);
  })();
  const puffs = Array.from({ length: 70 }, () => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: puffTex, transparent: true, depthWrite: false, opacity: 0, color: dark ? 0x9aa6b2 : 0xffffff }));
    s.userData = { life: 0, max: 1 }; scene.add(s); return s;
  });
  let puffIdx = 0;
  const emit = (x, y, z, spread = 0.25) => {
    const p = puffs[puffIdx++ % puffs.length];
    p.position.set(x + (Math.random() - 0.5) * spread, y, z + (Math.random() - 0.5) * spread);
    p.userData = { life: 0, max: 2.4 + Math.random(), vx: (Math.random() - 0.5) * 0.4, vy: -0.2 + Math.random() * 0.3, s0: 0.5 + Math.random() * 0.4 };
  };
  // Clouds that pass by give the climb and the descent a sense of height.
  const clouds = Array.from({ length: 14 }, (_, i) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: puffTex, transparent: true, depthWrite: false, opacity: dark ? 0.06 : 0.5 }));
    s.position.set((Math.random() - 0.5) * 50, 10 + i * 4.5, -12 - Math.random() * 20); s.scale.set(14 + Math.random() * 10, 4 + Math.random() * 3, 1);
    scene.add(s); return s;
  });

  // Timeline (seconds). The seed and morph play once; flights then repeat.
  const H = 40;                          // apogee in world units (the climb is compressed for the screen)
  const T = { seed: 3.6, morph: 1.1, wait: 0.7, boost: 2.4, apogee: 1.0, descent: 5.2, land: 1.6, refold: 0.9 };
  let t = 0, phase = "seed", flight = 1, spin = 0, spinRate = 0, camY = 3, last = performance.now(), running = true, visible = true;

  function setCaption(key) {
    if (!caption || caption.dataset.key === key) return;
    caption.dataset.key = key;
    caption.querySelector("b").textContent = CAPTIONS[key][0];
    caption.querySelector("span").textContent = CAPTIONS[key][1];
    caption.classList.remove("in"); void caption.offsetWidth; caption.classList.add("in");
  }

  function layout() {
    const w = host.clientWidth, h = host.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(layout).observe(host); layout();

  function pose(dt) {
    let y = 0, fold = 1, noseOff = 0, flameOn = false, rocketScale = 1, seedOn = false, tilt = 0;
    const u = (k) => Math.min(1, t / T[k]);
    if (phase === "seed") {
      seedOn = true; rocketScale = 0; setCaption("seed");
      const k = ease.inOut(u("seed"));
      seed.position.set(Math.sin(t * 2.2) * 0.6, 16 - 15.2 * k, Math.cos(t * 2.2) * 0.6);
      seed.rotation.y += dt * 11; seed.rotation.z = 0.35;
      if (t > T.seed) { phase = "morph"; t = 0; }
    } else if (phase === "morph") {
      setCaption("morph");
      const k = ease.smooth(u("morph"));
      seedOn = k < 0.98; seed.scale.setScalar(S * 2.2 * (1 - k)); seed.rotation.y += dt * 11 * (1 - k);
      rocketScale = ease.outBack(k);
      if (t > T.morph) { phase = "wait"; t = 0; }
    } else if (phase === "wait") {
      setCaption(flight === 1 ? "morph" : "land");
      if (t > T.wait) { phase = "boost"; t = 0; }
    } else if (phase === "boost") {
      setCaption("launch");
      const k = u("boost");
      y = H * (1 - Math.pow(1 - k, 2.2)) * Math.min(1, k * 3.2); // fast boost, long coast
      flameOn = k < 0.32;
      if (k < 0.5 && Math.random() < 0.9) emit(rocket.position.x, y - 0.4, 0, 0.15);
      if (k < 0.05) for (let i = 0; i < 3; i++) emit(0.2, 0.15, 0, 1.2);
      if (t > T.boost) { phase = "apogee"; t = 0; }
    } else if (phase === "apogee") {
      setCaption("apogee");
      const k = u("apogee");
      y = H - 0.8 * k * k;
      noseOff = ease.outBack(Math.min(1, k * 1.6)) * 90;
      fold = 1 - ease.outBack(Math.min(1, Math.max(0, (k - 0.15) / 0.75)));
      spinRate = 7 * ease.smooth(k);
      tilt = Math.sin(k * Math.PI) * 0.08;
      if (t > T.apogee) { phase = "descent"; t = 0; }
    } else if (phase === "descent") {
      setCaption("descent");
      const k = u("descent");
      y = (H - 0.8) * (1 - k) ; noseOff = 90; fold = 0; spinRate = 7;
      tilt = Math.sin(t * 3.1) * 0.03;
      if (t > T.descent) { phase = "land"; t = 0; }
    } else if (phase === "land") {
      setCaption("land");
      const k = u("land");
      y = 0; noseOff = 90 * (1 - ease.smooth(k)); fold = 0; spinRate = 7 * (1 - ease.smooth(Math.min(1, k * 2)));
      if (t > T.land) { phase = "refold"; t = 0; }
    } else if (phase === "refold") {
      setCaption("land");
      fold = ease.inOut(u("refold")); spinRate = 0;
      if (t > T.refold) { phase = "wait"; t = 0; flight += 1; if (counter) counter.textContent = String(flight).padStart(2, "0"); }
    }
    spin += spinRate * dt;
    rocket.position.set(0, y + 0.02, 0);
    rocket.rotation.set(tilt, spin, tilt * 0.6);
    rocket.scale.setScalar(S * Math.max(0.0001, rocketScale));
    seed.visible = seedOn;
    blades.forEach((b) => b.fold(fold));
    setNose(noseOff);
    flame.visible = flameOn; if (flameOn) flame.scale.set(1, 0.8 + Math.random() * 0.5, 1);
    // Camera follows height with a lag; the sky darkens a little as it climbs.
    const lift = camera.aspect < 0.9 ? 0.8 : 2.4;            // phones look straight at the rocket; wide screens look above it
    const target = phase === "seed" ? Math.max(2.8, seed.position.y * 0.6) : Math.max(2.8, y + lift);
    camY += (target - camY) * Math.min(1, dt * (phase === "boost" ? 7 : 3));
    const wide = camera.aspect > 1.15;
    const orbit = performance.now() / 1000 * 0.05;
    const off = wide ? 2.6 : camera.aspect < 0.9 ? 1.5 : 0; // right third on wide screens, right of the caption on phones
    const tx = -off * Math.cos(orbit), tz = off * Math.sin(orbit);
    const dist = camera.aspect < 0.9 ? 27 : 19;                // further back on portrait screens, so it fits below the copy
    camera.position.set(tx + Math.sin(orbit) * dist, camY + 2.2, tz + Math.cos(orbit) * dist);
    camera.lookAt(tx, camY, tz);
    host.style.setProperty("--alt", Math.min(1, camY / H).toFixed(3));
    lights.key.position.set(3, camY + 6, 4); lights.key.target.position.set(0, camY, 0); lights.key.target.updateMatrixWorld();
    for (const p of puffs) {
      const d = p.userData; if (d.life >= d.max) { p.material.opacity = 0; continue; }
      d.life += dt; const a = d.life / d.max;
      p.position.x += d.vx * dt; p.position.y += d.vy * dt;
      const s = d.s0 + a * 1.6; p.scale.set(s, s, 1); p.material.opacity = 0.55 * (1 - a);
    }
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (running && visible) { t += dt; pose(dt); renderer.render(scene, camera); }
    requestAnimationFrame(frame);
  }

  function still() { // reduced motion: rotor open, hovering above the pad, no movement
    phase = "descent"; t = T.descent * 0.72; pose(0); spin = 0.6; pose(0); setCaption("descent"); renderer.render(scene, camera);
  }

  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0.02 });
  io.observe(host);
  document.addEventListener("visibilitychange", () => { last = performance.now(); });
  pauseBtn?.addEventListener("click", () => {
    running = !running; last = performance.now();
    pauseBtn.setAttribute("aria-pressed", String(!running));
    pauseBtn.querySelector("span").textContent = running ? "Pause" : "Play";
  });
  const apply = () => {
    if (reduce.matches) { running = false; pauseBtn?.setAttribute("hidden", ""); still(); }
    else { running = true; pauseBtn?.removeAttribute("hidden"); }
  };
  reduce.addEventListener("change", apply); apply();
  host.classList.add("hero--ready");
  // Deterministic stepping for tools/render.mjs (README frames). Not used by the page itself.
  window.__hero = {
    step(n, dt = 1 / 30) { running = false; for (let i = 0; i < n; i++) { t += dt; pose(dt); } renderer.render(scene, camera); return phase; },
    reset() { t = 0; phase = "seed"; flight = 1; spin = 0; spinRate = 0; camY = 3; seed.scale.setScalar(S * 2.2); },
  };
  requestAnimationFrame(frame);
}
