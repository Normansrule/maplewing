// Maplewing 3D: loads the real CAD parts (cad/stl, copied to docs/models) and assembles them (MIT).
// Shared by the hero animation, the parts viewer and tools/render.mjs, so every picture is the CAD.
import * as THREE from "three";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { toCreasedNormals } from "three/addons/utils/BufferGeometryUtils.js";

const loader = new STLLoader();
const cache = new Map();

/** Load one STL from docs/models, centred on nothing (CAD origin kept), in millimetres. */
export function loadPart(name, base = "") {
  if (!cache.has(name)) {
    cache.set(name, new Promise((ok, bad) => loader.load(`${base}models/${name}.stl`, (g) => {
      ok(toCreasedNormals(g, Math.PI / 6)); // smooth curved walls, keep sharp printed edges
    }, undefined, bad)));
  }
  return cache.get(name);
}

/** Materials in the Maplewing palette: carbon, white, one maple red, and natural balsa. */
export function materials(dark = false) {
  return {
    carbon: new THREE.MeshPhysicalMaterial({ color: 0x15171a, roughness: 0.38, metalness: 0.1, clearcoat: 0.9, clearcoatRoughness: 0.18 }),
    white: new THREE.MeshPhysicalMaterial({ color: 0xf3f4f2, roughness: 0.42, clearcoat: 0.55, clearcoatRoughness: 0.25 }),
    red: new THREE.MeshPhysicalMaterial({ color: dark ? 0xc8352a : 0xb0201a, roughness: 0.35, clearcoat: 0.6, clearcoatRoughness: 0.2 }),
    balsa: new THREE.MeshPhysicalMaterial({ color: 0xd9bd8a, roughness: 0.78, sheen: 0.4, sheenColor: new THREE.Color(0xfff3dc) }),
    seed: new THREE.MeshPhysicalMaterial({ color: 0xa8503a, roughness: 0.6, sheen: 0.6, sheenColor: new THREE.Color(0xffd0b8) }),
    wing: new THREE.MeshPhysicalMaterial({ color: 0xc98a4a, roughness: 0.7, transmission: 0.15, thickness: 0.4, side: THREE.DoubleSide }),
    flame: new THREE.MeshBasicMaterial({ color: 0xffb070, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }),
  };
}

/** Material for a single part shown on its own (viewer and renders). */
export function partMaterial(id, M) {
  if (id.endsWith("rotor_blade")) return M.balsa;
  if (id.endsWith("rotor_hub")) return M.red;
  if (id.endsWith("ring_tail")) return M.carbon;
  return M.white;
}

function ogive(radius, length, segs = 48) {
  const pts = [];
  const rho = (radius * radius + length * length) / (2 * radius);
  for (let i = 0; i <= 32; i++) {
    const x = (length * i) / 32; // from tip
    const y = Math.sqrt(rho * rho - (length - x) ** 2) + radius - rho;
    pts.push(new THREE.Vector2(Math.max(0.0001, y), length - x));
  }
  return new THREE.LatheGeometry(pts, segs);
}

/**
 * Seedling, assembled from its CAD: printed ring tail and rotor hub, three balsa blades,
 * a BT-50 tube and an ogive nose. Z is up in the CAD; the group is rotated so +Y is up.
 * Returns handles the animations use: blades (with fold(t)), nose, flame.
 */
export async function buildSeedling(base = "", M = materials()) {
  const [tailG, hubG, bladeG] = await Promise.all(["seedling_ring_tail", "seedling_rotor_hub", "seedling_rotor_blade"].map((n) => loadPart(n, base)));
  const tubeOD = 24.8, tubeL = 420, hubZ = 355, noseL = 78;
  const rocket = new THREE.Group();          // CAD frame (mm, Z up)
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(tubeOD / 2, tubeOD / 2, tubeL, 64, 1, false), M.white);
  tube.rotation.x = Math.PI / 2; tube.position.z = tubeL / 2;
  const tail = new THREE.Mesh(tailG, M.carbon);
  const hub = new THREE.Mesh(hubG, M.red); hub.position.z = hubZ;
  const nose = new THREE.Group();
  const cone = new THREE.Mesh(ogive(tubeOD / 2, noseL), M.white); cone.rotation.x = Math.PI / 2;
  const band = new THREE.Mesh(new THREE.CylinderGeometry(tubeOD / 2 + 0.2, tubeOD / 2 + 0.2, 6, 64), M.red);
  band.rotation.x = Math.PI / 2; band.position.z = 3;
  nose.add(cone, band); nose.position.z = tubeL;
  const motor = new THREE.Mesh(new THREE.CylinderGeometry(9, 9, 6, 32), M.carbon);
  motor.rotation.x = Math.PI / 2; motor.position.z = -2;
  // Hinge: pads sit at the hub's outer face, pin hole at mid height (cad/maplewing_parts.py rotor_hub()).
  const P = { pin: 1.6, hubH: 12, padR: tubeOD / 2 + 0.3 / 2 + 0.8 + 1.6 * 3 - 0.3 };
  const blades = [];
  for (let k = 0; k < 3; k++) {
    const az = new THREE.Group(); az.rotation.z = (2 * Math.PI * k) / 3; az.position.z = hubZ + P.hubH / 2;
    const hinge = new THREE.Group(); hinge.position.x = P.padR;       // hinge axis = local Y (tangential)
    const pitch = new THREE.Group(); pitch.rotation.x = THREE.MathUtils.degToRad(6); // fixed 6 deg pitch
    const blade = new THREE.Mesh(bladeG, M.balsa);
    blade.position.set(P.pin * 2.5, 0, -0.8);                           // tab hole on the hinge axis
    pitch.add(blade); hinge.add(pitch); az.add(hinge); rocket.add(az);
    blades.push({ hinge, fold(t) { hinge.rotation.y = t * (Math.PI / 2 - 0.03); } }); // t=1 folded down along the tube
  }
  const flame = new THREE.Mesh(new THREE.ConeGeometry(7, 70, 24, 1, true), M.flame);
  flame.rotation.x = -Math.PI / 2; flame.position.z = -38; flame.visible = false;
  // Shock cord from the tube to the nose, so a deployed nose stays tethered (scaled by setNose()).
  const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 1, 6), M.red);
  cord.rotation.x = Math.PI / 2; cord.position.set(4, 0, tubeL); cord.visible = false;
  rocket.add(tube, tail, hub, nose, motor, flame, cord);
  rocket.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  const root = new THREE.Group(); root.rotation.x = -Math.PI / 2; root.add(rocket);
  const out = new THREE.Group(); out.add(root);
  out.userData = {
    blades, nose, flame, rocket, length: tubeL + noseL, noseRest: tubeL,
    setNose(off) { nose.position.z = tubeL + off; cord.visible = off > 2; cord.scale.y = Math.max(0.01, off); cord.position.z = tubeL + off / 2; },
  };
  blades.forEach((b) => b.fold(1));
  return out;
}

/**
 * Dewdrop, the water rocket: a 2 L PET bottle (drawn), printed ring-tail sleeve, rotor hub and the
 * nose with its timer bay, three balsa blades. Nozzle down. Same frame conventions as buildSeedling.
 */
export async function buildDewdrop(base = "", M = materials()) {
  const [tailG, hubG, bladeG, noseG] = await Promise.all(["dewdrop_ring_tail", "dewdrop_rotor_hub", "dewdrop_rotor_blade", "dewdrop_nose_timer_bay"].map((n) => loadPart(n, base)));
  const R = 52.5;
  const prof = [[0, 0], [11, 0], [11, 22], [13, 24], [16, 34], [34, 58], [48, 78], [R, 96], [R, 300], [R - 1, 304]].map(([r, z]) => new THREE.Vector2(r, z));
  const pet = new THREE.MeshPhysicalMaterial({ color: 0xdfeefa, roughness: 0.05, transmission: 0.92, thickness: 0.6, ior: 1.57, clearcoat: 1, side: THREE.DoubleSide });
  const bottle = new THREE.Mesh(new THREE.LatheGeometry(prof, 72), pet); bottle.rotation.x = Math.PI / 2;
  const water = new THREE.Mesh(new THREE.CylinderGeometry(R - 2, R - 2, 70, 64), new THREE.MeshPhysicalMaterial({ color: 0x9cc7ea, roughness: 0.1, transmission: 0.7, thickness: 2 }));
  water.rotation.x = Math.PI / 2; water.position.z = 132;
  const rocket = new THREE.Group();
  const tail = new THREE.Mesh(tailG, M.carbon); tail.position.z = 100;
  const hub = new THREE.Mesh(hubG, M.red); hub.position.z = 262;
  const nose = new THREE.Mesh(noseG, M.white); nose.position.z = 296;
  const padR = R + 0.3 + 1.2 + 2.1 * 3 - 0.3;
  const blades = [];
  for (let k = 0; k < 3; k++) {
    const az = new THREE.Group(); az.rotation.z = (2 * Math.PI * k) / 3 + Math.PI / 3; az.position.z = 262 + 8;
    const hinge = new THREE.Group(); hinge.position.x = padR;
    const pitch = new THREE.Group(); pitch.rotation.x = THREE.MathUtils.degToRad(6);
    const blade = new THREE.Mesh(bladeG, M.balsa); blade.position.set(2.1 * 2.5, 0, -1.6);
    pitch.add(blade); hinge.add(pitch); az.add(hinge); rocket.add(az);
    blades.push({ hinge, fold(t) { hinge.rotation.y = t * (Math.PI / 2 - 0.03); } });
  }
  rocket.add(bottle, water, tail, hub, nose);
  rocket.traverse((o) => { if (o.isMesh) { o.castShadow = o.material !== pet; o.receiveShadow = true; } });
  const root = new THREE.Group(); root.rotation.x = -Math.PI / 2; root.add(rocket);
  const out = new THREE.Group(); out.add(root);
  out.userData = { blades, nose, rocket };
  return out;
}

/** A maple samara (seed): a nut and one veined wing, for the first seconds of the hero. */
export function buildSamara(M = materials()) {
  const g = new THREE.Group();
  const nut = new THREE.Mesh(new THREE.SphereGeometry(9, 32, 24), M.seed); nut.scale.set(1.25, 0.8, 0.9);
  const shape = new THREE.Shape();
  shape.moveTo(0, -6); shape.bezierCurveTo(40, -16, 95, -10, 118, 4);
  shape.bezierCurveTo(124, 14, 112, 22, 96, 22); shape.bezierCurveTo(60, 20, 30, 14, 0, 7); shape.closePath();
  const wing = new THREE.Mesh(new THREE.ShapeGeometry(shape, 24), M.wing);
  wing.rotation.x = -Math.PI / 2 + 0.55; // coned, as a falling samara is
  g.add(nut, wing);
  g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  return g;
}

/** Studio lighting used by every view: soft key, cool fill, warm rim, environment for reflections. */
export function studio(renderer, scene, { shadows = true } = {}) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  return import("three/addons/environments/RoomEnvironment.js").then(({ RoomEnvironment }) => {
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(3, 6, 4);
    if (shadows) {
      key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.radius = 6; key.shadow.bias = -0.0004;
      Object.assign(key.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4, near: 0.5, far: 30 });
    }
    const rim = new THREE.DirectionalLight(0xffd9c4, 1.1); rim.position.set(-5, 3, -4);
    const fill = new THREE.HemisphereLight(0xdfeefc, 0x2a2622, 0.55);
    scene.add(key, rim, fill);
    return { key, rim, fill };
  });
}
