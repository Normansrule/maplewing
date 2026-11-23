#!/usr/bin/env python3
"""Builds the generated parts of the website and desktop app from the repo's own data (MIT licence).

  sim/lineup.json + cad/parts.json + exports/bom/maplewing-bom.csv  ->  docs/data/site-data.js
  cad/stl/*.stl                                                    ->  docs/models/  (served by Pages)
  web/ (configurator source)                                       ->  docs/app/index.html

Nothing here invents a number: every figure on the site comes from the simulator output, the CAD
report or the parts list. Maplewing-3 is held for export-control review and must never appear.
Run from the repo root:  python3 tools/build_site.py      (make site)
"""
from __future__ import annotations
import csv, json, pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

STATUS = {  # what each rocket is today. Nothing has been bought, built or flown.
    "Taproot": ("ready", "Ready to build: off-the-shelf Estes kit, the control airframe"),
    "Seedling": ("ready", "Ready to build: CAD and ground tests written, waiting on go-ahead"),
    "Dewdrop": ("ready", "Ready to build: CAD and test plan written, waiting on go-ahead"),
    "Maplewing-1": ("paper", "Paper only: altimeter charges wait on the energetics rule"),
    "Maplewing-1 L2 config": ("paper", "Paper only: Level 2 configuration of Maplewing-1"),
    "Maplewing-2": ("sim", "Simulation only: two-stage Level 3 study"),
}
BLURB = {
    "Taproot": "A classic three-fin model rocket with a parachute. It flies first, so every ring-tail and rotor result has a control to beat.",
    "Seedling": "The rotor pathfinder: a BT-50 tube, a printed ring tail and a 0.30 m rotor pushed out by the motor's own ejection charge.",
    "Dewdrop": "A 2 L water rocket with a printed ring tail and a spring-folded rotor released by a wind-up timer. No pyro at all.",
    "Maplewing-1": "The first high-power Maplewing: a 54 mm airframe on an H128W reload, rotor plus backup parachute from two commercial altimeters.",
    "Maplewing-1 L2 config": "The same airframe family scaled to 102 mm for a J350W reload and a Level 2 flight.",
    "Maplewing-2": "Two Core-98 stages that share avionics, rotor and fin modules. Every stage lands on its own rotor.",
}
PART_TITLES = {
    "ring_tail": "Ring tail", "rotor_hub": "Rotor hub", "rotor_blade": "Rotor blade", "nose_timer_bay": "Nose with timer bay",
}
ROCKET_OF = {"seedling": "Seedling", "dewdrop": "Dewdrop", "maplewing1": "Maplewing-1"}


def lineup() -> list[dict]:
    data = json.loads((ROOT / "sim" / "lineup.json").read_text())
    ring = {r["vehicle"]["name"]: r for r in data["ring"]}
    out = []
    for r in data["fins"]:  # default lineup: ring tails on subsonic rockets, fins on supersonic stages
        v, f, c = r["vehicle"], r["flight"], r["class"]
        name = v["name"]
        assert "Maplewing-3" not in name, "Maplewing-3 is held for export review"
        land = r["landing"]
        stages = []
        for s, L in zip(v["stages"], land):
            stages.append({
                "name": s["name"], "d_mm": round(s["d"] * 1000), "tail": s["tail"], "motor": s.get("motor"),
                "landing": L["primary"], "landing_D_m": L["primary_D_m"], "v_land_ms": L["v_land_ms"],
                "landing_J": L["landing_J"], "backup_D_m": L.get("backup_D_m"),
                "mass_kg": round(sum(m["mass"] for m in s["modules"]), 3),
            })
        status, note = STATUS[name]
        item = {
            "name": name, "tier": v["tier"], "faa": c["faa_class"], "cert": c["cert_level"],
            "impulse_Ns": c["total_impulse_Ns"], "apogee_m": f["apogee_m"], "vmax_ms": f["vmax_ms"],
            "mach": f["mach_max"], "t_apogee_s": f.get("t_apogee_s"), "stages": stages,
            "status": status, "status_note": note, "blurb": BLURB[name], "errors": r["errors"],
            "ring_apogee_m": ring[name]["flight"]["apogee_m"] if name in ring else None,
        }
        if v.get("water"):
            item["water"] = v["water"]
        if "ejection" in f:
            item["ejection"] = f["ejection"]
        out.append(item)
    return out


def parts() -> dict:
    p = json.loads((ROOT / "cad" / "parts.json").read_text())
    rows = []
    for key, r in p["parts"].items():
        rocket_key, kind = key.split("_", 1)
        rows.append({
            "id": key, "title": PART_TITLES[kind], "rocket": ROCKET_OF[rocket_key], "qty": r["qty"],
            "material": r["material"], "mass_g": r["mass_g_each"], "budget_g": r["budget_g"],
            "bbox_mm": r["bbox_mm"], "shared_id": r["shared_id"], "stl": f"models/{key}.stl",
            "img": f"assets/renders/{key}.png", "paper_only": rocket_key == "maplewing1",
            "how": "Cut from balsa sheet using the STL outline" if r["material"] == "balsa" else "Print in PETG",
        })
    return {"pitch_deg": p["pitch_deg"], "parts": rows,
            "params": {k: p[k] for k in ("seedling", "water", "maplewing1")}}


def bom() -> list[dict]:
    with open(ROOT / "exports" / "bom" / "maplewing-bom.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("unit_price_usd", "line_usd"):
            r[k] = float(r[k]) if r[k] else None
        r["qty"] = int(r["qty"])
    return rows


def build_app() -> None:
    """The configurator (web/) becomes docs/app/index.html, with the lineup data inlined."""
    subprocess.run([sys.executable, str(ROOT / "sim" / "build_configurator.py")], check=True, cwd=ROOT / "sim")
    src = (ROOT / "web" / "dist" / "configurator.html").read_text()
    (DOCS / "app").mkdir(parents=True, exist_ok=True)
    (DOCS / "app" / "index.html").write_text(src)


def main() -> None:
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    (DOCS / "models").mkdir(parents=True, exist_ok=True)
    for stl in sorted((ROOT / "cad" / "stl").glob("*.stl")):
        shutil.copy2(stl, DOCS / "models" / stl.name)
    rows = bom()
    # Stamp with the newest price-check date, not today, so a rebuild with unchanged data is byte-identical (CI checks this).
    data = {"prices_checked": max((r["checked"] for r in rows if r["checked"]), default=""), "lineup": lineup(), "cad": parts(), "bom": rows,
            "rotor": {"C_rotor": 1.08, "C_chute": 1.5, "v_target_ms": 6.5, "pitch_deg": 6.0}}
    blob = json.dumps(data, separators=(",", ":"))
    assert "Maplewing-3" not in blob and "O8000" not in blob
    (DOCS / "data" / "site-data.js").write_text(
        "// Generated by tools/build_site.py from sim/lineup.json, cad/parts.json and exports/bom/maplewing-bom.csv. Do not edit.\n"
        f"window.MAPLEWING={blob};\n")
    build_app()
    print(f"site data: {len(data['lineup'])} rockets, {len(data['cad']['parts'])} parts, {len(data['bom'])} BOM rows")


if __name__ == "__main__":
    main()
