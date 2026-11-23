// Parts inspector: orbit any printable part in 3D, read its numbers, download its STL (MIT).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { loadPart, materials, partMaterial, studio, buildSeedling } from "./rocket3d.js";

const dlg = document.querySelector("[data-inspector]");
if (dlg) init();

function init() {
  const canvas = dlg.querySelector("canvas");
  const title = dlg.querySelector("[data-title]");
  const facts = dlg.querySelector("[data-facts]");
  const dl = dlg.querySelector("[data-download]");
  let renderer, scene, camera, controls, mesh, raf = 0, ready;

  async function setup() {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.shadowMap.enabled = true;
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(30, 1, 0.01, 100);
    controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.autoRotate = !matchMedia("(prefers-reduced-motion: reduce)").matches; controls.autoRotateSpeed = 1.2;
    await studio(renderer, scene);
    const floor = new THREE.Mesh(new THREE.CircleGeometry(4, 48), new THREE.ShadowMaterial({ opacity: 0.16 }));
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; floor.name = "floor"; scene.add(floor);
  }

  function size() {
    const r = canvas.getBoundingClientRect();
    renderer.setSize(r.width, r.height, false); camera.aspect = r.width / r.height; camera.updateProjectionMatrix();
  }

  async function show(part) {
    ready ??= setup(); await ready;
    if (mesh) { scene.remove(mesh); }
    const M = materials(document.documentElement.dataset.theme === "dark" || (matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light"));
    if (part.id === "seedling_assembly") {
      mesh = await buildSeedling("", M);
      mesh.userData.blades.forEach((b) => b.fold(0));
      mesh.scale.setScalar(0.01);
    } else {
      const g = await loadPart(part.id);
      const m = new THREE.Mesh(g, partMaterial(part.id, M)); m.castShadow = true;
      const holder = new THREE.Group(); holder.rotation.x = -Math.PI / 2; holder.add(m);
      mesh = new THREE.Group(); mesh.add(holder);
      const longest = Math.max(...part.bbox_mm);
      mesh.scale.setScalar(2.4 / longest);
    }
    scene.add(mesh);
    const box = new THREE.Box3().setFromObject(mesh);
    const c = box.getCenter(new THREE.Vector3());
    mesh.position.sub(new THREE.Vector3(c.x, box.min.y, c.z));
    const h = box.max.y - box.min.y, rad = box.getBoundingSphere(new THREE.Sphere()).radius;
    controls.target.set(0, h / 2, 0);
    camera.position.set(rad * 2.2, h / 2 + rad * 1.3, rad * 2.9);
    controls.update();
    size();
    cancelAnimationFrame(raf);
    const loop = () => { controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(loop); };
    loop();
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-part]");
    if (!btn) return;
    const all = window.MAPLEWING.cad.parts;
    const part = btn.dataset.part === "seedling_assembly"
      ? { id: "seedling_assembly", title: "Seedling, assembled", rocket: "Seedling", bbox_mm: [300, 300, 500] }
      : all.find((p) => p.id === btn.dataset.part);
    title.textContent = `${part.rocket} · ${part.title}`;
    facts.innerHTML = part.mass_g == null
      ? `<div><dt>What you see</dt><dd>Printed ring tail and hub, three balsa blades, BT-50 tube and nose. Rotor shown open.</dd></div>`
      : `<div><dt>Material</dt><dd>${part.material === "balsa" ? "Balsa sheet, cut to outline" : "PETG, printed"}</dd></div>
         <div><dt>Quantity</dt><dd>${part.qty}</dd></div>
         <div><dt>Mass (CAD)</dt><dd>${part.mass_g} g <small>budget ${part.budget_g} g</small></dd></div>
         <div><dt>Size</dt><dd>${part.bbox_mm.map((v) => Math.round(v)).join(" × ")} mm</dd></div>
         <div><dt>Shared module</dt><dd>${part.shared_id}</dd></div>
         ${part.paper_only ? `<div><dt>Status</dt><dd>Paper only: print to check fit, not to fly</dd></div>` : ""}`;
    if (part.stl) { dl.href = part.stl; dl.setAttribute("download", `${part.id}.stl`); dl.hidden = false; } else dl.hidden = true;
    dlg.showModal();
    show(part);
  });
  dlg.addEventListener("close", () => cancelAnimationFrame(raf));
  window.addEventListener("resize", () => { if (dlg.open) size(); });
}
