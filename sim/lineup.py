#!/usr/bin/env python3
"""The five Maplewing rockets, built from the shared framework (MIT licence).

  1  Taproot      FAA Class 1 model rocket, 3 fins, parachute, Estes C6-5 (the affordable control)
  2  Dewdrop      water rocket, ring tail, spring-folded rotor
  3  Maplewing-1  single stage, ring tail, rotor + backup chute (L1 H128W; L2 J350W config)
  4  Maplewing-2  two stage, FAA Class 2: O3400 booster + N5600 sustainer (98 mm "Core-98" modules)
  (Maplewing-3, a three-stage FAA Class 3 study, is held for export-control review and is not in the public repo.)

Reuse by design: the Core-98 booster and sustainer share their avionics, rotor and fin modules;
all HPR motors except the water/Estes rungs are reloads, so the motor cases are reused too.
Every stage lands on its own (rotor or parachute). Run: python3 lineup.py -> lineup.json
"""
from __future__ import annotations
import json, pathlib
from maplewing_framework import Module, Landing, Stage, Vehicle, validate, classify, fly, size_landing, to_json, ejection_options
import phase0_compare as pc

RING = 1.35   # ring-tail drag factor vs fins (Phase 0 ratio), ASSUMED
HPR_LAND = dict(deploy="commercial_altimeter", redundant_altimeters=True)
AIRSTART = dict(ignition="commercial_altimeter", inhibits=("altitude", "tilt", "time"))

def core98_booster(tail):  # shared_id CORE-98-B: Maplewing-2 booster
    return Stage("Core-98 booster (O3400)", 0.102, 0.45 * (RING if tail == "ring" else 1), tail,
                 [Module("motor_mount", 0.6, "MM-98"), Module("body", 0.9, "BT-98-B"), Module("interstage", 0.4, "IS-98"),
                  Module("ring_tail" if tail == "ring" else "fins", 0.7, f"TAIL-98-{tail}"),
                  Module("avbay", 0.8, "AV-98"), Module("rotor_bay", 0.6, "RB-98")],
                 Landing("rotor", "parachute", **HPR_LAND), motor="O3400")

def core98_sustainer(tail):
    return Stage("Core-98 sustainer (N5600)", 0.102, 0.40 * (RING if tail == "ring" else 1), tail,
                 [Module("nose", 0.6, "NC-98"), Module("avbay", 0.8, "AV-98"), Module("rotor_bay", 0.6, "RB-98"),
                  Module("chute_bay", 0.4, "CB-98"), Module("body", 1.4, "BT-98-S"),
                  Module("ring_tail" if tail == "ring" else "fins", 0.7, f"TAIL-98-{tail}")],
                 Landing("rotor", "parachute", drogue=True, **HPR_LAND), motor="N5600", **AIRSTART)

def lineup(tail_hpr="ring"):
    taproot = Vehicle("Taproot", "Class 1 normal", [Stage("Taproot", 0.0248, 0.643, "fins",
        [Module("nose", 0.006, "NC-BT50", metal=False), Module("body", 0.020, "BT-50"), Module("fins", 0.005, "FIN-3"),
         Module("chute_bay", 0.003, "CB-BT50")],
        Landing("parachute", None, "motor_ejection", primary_d=0.305), motor="C6", delay_s=5)])
    # Seedling: the Phase 0 rotor pathfinder (not one of the five). BT-50 ring tail, 0.30 m rotor
    # pushed out by motor ejection. Ring/hub/blade masses from cad/parts.json; the rest ASSUMED
    # to match the Phase 0 68 g airframe until parts are weighed.
    seedling = Vehicle("Seedling", "Class 1 rotor pathfinder", [Stage("Seedling", 0.0248, 0.70, "ring",
        [Module("nose", 0.006, "NC-BT50", metal=False), Module("body", 0.030, "BT-50-S"), Module("motor_mount", 0.008, "MM-18"),
         Module("rotor_bay", 0.013, "RB-BT50"), Module("ring_tail", 0.0111, "TAIL-BT50-ring")],
        Landing("rotor", None, "motor_ejection", primary_d=0.30), motor="C6", delay_s=5)])
    dewdrop = Vehicle("Dewdrop", "Water", [Stage("Dewdrop", 0.105, 0.55, "ring",
        [Module("bottle", 0.050, "PET-2L"), Module("nose", 0.0367, "NC-W"), Module("rotor_bay", 0.0245, "RB-W"),
         Module("ring_tail", 0.0485, "TAIL-W-ring")],  # masses from cad/parts.json (CadQuery v2)
        Landing("rotor", None, "mechanical_timer", primary_d=0.44))],
        water={"psi": 60, "water_l": 0.6, "bottle": "PET", "remote_release": True, "proof_psi": 90})
    mw1 = Vehicle("Maplewing-1", "Single stage", [Stage("Maplewing-1 L1 (H128W)", 0.0574, 0.65, "ring",
        [Module("nose", 0.15, "NC-54"), Module("avbay", 0.35, "AV-54"), Module("rotor_bay", 0.30, "RB-54"),
         Module("chute_bay", 0.12, "CB-54"), Module("body", 0.25, "BT-54"), Module("ring_tail", 0.25, "TAIL-54-ring")],
        Landing("rotor", "parachute", **HPR_LAND), motor="H128W")])
    mw1_l2 = Vehicle("Maplewing-1 L2 config", "Single stage", [Stage("Maplewing-1 L2 (J350W)", 0.1016, 0.62, "ring",
        [Module("nose", 0.45, "NC-102"), Module("avbay", 0.8, "AV-102"), Module("rotor_bay", 0.6, "RB-102"),
         Module("chute_bay", 0.35, "CB-102"), Module("body", 0.8, "BT-102"), Module("ring_tail", 0.6, "TAIL-102-ring")],
        Landing("rotor", "parachute", **HPR_LAND), motor="J350W")])
    mw2 = Vehicle("Maplewing-2", "Class 2 two stage", [core98_booster(tail_hpr), core98_sustainer(tail_hpr)], site_alt=1190)
    return [taproot, seedling, dewdrop, mw1, mw1_l2, mw2]

def best_water_fill():
    """Sweep water fill at 60 psi for the Dewdrop airframe (best fill is usually about 1/3)."""
    res = []
    for f in range(300, 1001, 50):
        try:
            a = pc.water_rocket(60, V_water=f / 1e6, dry=0.150)["apogee_m"]
        except TypeError:   # the simplified air-pulse model breaks down at high fills
            continue
        res.append((f, a))
    return max(res, key=lambda x: x[1])

def run(tail_hpr="ring"):
    rows = []
    for v in lineup(tail_hpr):
        errs = validate(v); c = classify(v); f = fly(v)
        lands = [size_landing(s, v.site_alt) for s in v.stages]
        row = {"vehicle": to_json(v), "errors": errs, "class": c, "flight": f, "landing": lands}
        if "ejection" in f:
            row["ejection_options"] = ejection_options(v)
        rows.append(row)
    return rows

def main():
    # Default ("fins"): ring tails only on subsonic rockets, fins on every supersonic stage, because
    # nobody has ring-tail data above Mach 1 (open question 2). "ring" is the all-ring comparison.
    out = {"ring": run("ring"), "fins": run("fins"), "water_best_fill": best_water_fill()}
    json.dump(out, open(pathlib.Path(__file__).with_name("lineup.json"), "w"), indent=1)
    for tail in ("ring", "fins"):
        print(f"\n== HPR multistage tails: {tail}")
        for r in out[tail]:
            v, c, f = r["vehicle"], r["class"], r["flight"]
            print(f"{v['name']:<24} {c['faa_class']:<32} {c['cert_level']:<14} apogee {f['apogee_m']/1000:>6.2f} km  Mach {f['mach_max']:<4} rules {'PASS' if not r['errors'] else r['errors']}")
            for L in r["landing"]:
                print(f"     {L['stage']:<58} {L['primary']:<9} D {L['primary_D_m']:>4} m  {L['v_land_ms']:>4} m/s  {L['landing_J']:>6} J"
                      + (f"   backup chute {L['backup_D_m']} m" if 'backup_D_m' in L else ""))
    for r in out["fins"]:
        for o in r.get("ejection_options", []):
            print(f"{r['vehicle']['name']} delay {o['delay_s']} s: ejects at {o['t_s']} s, {o['alt_m']} m, {o['v_ms']:+} m/s (apogee {r['flight']['t_apogee_s']} s)")
    print("\nDewdrop best water fill at 60 psi: %d mL -> %.1f m" % out["water_best_fill"])

if __name__ == "__main__":
    main()
