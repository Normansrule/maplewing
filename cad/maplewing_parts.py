#!/usr/bin/env python3
"""Maplewing parametric parts in CadQuery (CAD, data and STL under CC BY-SA 4.0; code MIT).

Only parts that can be built and flown today without handling energetics:
  * Dewdrop (water rocket): ring-tail sleeve, rotor hub, rotor blade, nose with timer bay
  * Seedling (A-D model rocket, motor-ejection deployment): ring tail, rotor hub, rotor blade

Rotor sizes come from sim/rotor_bem.py (Water 0.44 m, Seedling 0.30 m, 3 blades, fixed pitch).
Pitch is FIXED by the printed hinge-pad angle: there is nothing that can change it in flight.
All dimensions in mm. MEASURE your bottle and body tube and change the parameters before printing.

Run (Ubuntu / WSL2):  python3 -m venv ~/.venvs/cq && ~/.venvs/cq/bin/pip install cadquery
                      ~/.venvs/cq/bin/python cad/maplewing_parts.py   -> cad/stl/*.stl + cad/parts.json
"""
from __future__ import annotations
import json, math, pathlib
import cadquery as cq

OUT = pathlib.Path(__file__).resolve().parent
PETG_G_CM3 = 1.27          # solid PETG density; thin walls print near 100 % solid
BALSA_G_CM3 = 0.16         # light/medium balsa sheet, typical; weigh your sheet
# Version 1 printed everything at 1.6-2 mm walls and came out 2.6x over the mass budget
# (Dewdrop 262 g of parts vs 100 g assumed). Version 2: thin walls (vase-mode nose), balsa blades.
PITCH_DEG = 6.0            # best fixed pitch from rotor_bem.py

# ------------------------------------------------------------------ parameters (mm)
WATER = dict(
    bottle_od=105.0,       # 2 L PET body; measure yours (typically about 100-110 mm)
    fit=0.6,               # diametral clearance for a slip fit, then tape
    sleeve_h=30.0, wall=1.0,
    ring_od=165.0, ring_chord=45.0, ring_wall=1.0, struts=3, strut_t=2.0,
    rotor_d=440.0, blades=3, root_cutout=30.0, chord=35.0, blade_t=3.2,   # 1/8 in balsa sheet
    hub_h=16.0, hub_wall=1.2, pin_d=2.1, nose_wall=0.8,  # 2 mm hinge pin (steel music wire or a printed pin)
    nose_len=110.0, timer_bay=(34.0, 34.0, 24.0),  # pocket for a small wind-up timer, W x L x H
)
SEEDLING = dict(
    tube_od=24.8, fit=0.3,  # Estes BT-50 class
    sleeve_h=25.0, wall=0.8,
    ring_od=58.0, ring_chord=40.0, ring_wall=0.8, struts=3, strut_t=1.2,   # 55 mm mean ring from phase0
    rotor_d=300.0, blades=3, root_cutout=15.0, chord=25.0, blade_t=1.6,   # 1/16 in balsa sheet
    hub_h=12.0, hub_wall=0.8, pin_d=1.6,
)

# Maplewing-1 (54 mm class, H128W). PAPER ONLY: its rotor and backup chute deploy on a commercial
# altimeter's charges, which is an open decision. Printing parts to check fit is harmless.
MAPLEWING1 = dict(
    tube_od=57.4, fit=0.4,  # 54 mm airframe tube, about 57.4 mm OD; measure yours
    sleeve_h=60.0, wall=1.6,
    ring_od=115.0, ring_chord=80.0, ring_wall=1.6, struts=3, strut_t=2.4,   # ring about 2x body, as phase0
    rotor_d=880.0, blades=3, root_cutout=40.0, chord=60.0, blade_t=4.8,    # 3/16 in balsa; framework sizes 0.88 m
    hub_h=24.0, hub_wall=2.0, pin_d=3.1,   # 3 mm steel hinge pin
)

# ------------------------------------------------------------------ parts
def ring_tail(p, body_od):
    """Sleeve that slides over the body, three radial struts, and the annular fin (ring)."""
    sid = body_od + p["fit"]
    sleeve = cq.Workplane("XY").circle(sid / 2 + p["wall"]).circle(sid / 2).extrude(p["sleeve_h"])
    ring = (cq.Workplane("XY").workplane(offset=(p["sleeve_h"] - p["ring_chord"]) / 2)
            .circle(p["ring_od"] / 2).circle(p["ring_od"] / 2 - p["ring_wall"]).extrude(p["ring_chord"]))
    span = (p["ring_od"] / 2 - p["ring_wall"] / 2) - (sid / 2 + p["wall"] / 2)
    strut = (cq.Workplane("XY").center(sid / 2 + p["wall"] / 2 + span / 2, 0)
             .rect(span, p["strut_t"]).extrude(p["sleeve_h"]))
    part = sleeve.union(ring)
    for k in range(p["struts"]):
        part = part.union(strut.rotate((0, 0, 0), (0, 0, 1), 360 / p["struts"] * k))
    return part

def rotor_hub(p, body_od):
    """Collar with one hinge pad per blade. Each pad is tilted by PITCH_DEG, which fixes the pitch."""
    sid = body_od + p["fit"]
    hub = cq.Workplane("XY").circle(sid / 2 + p["hub_wall"]).circle(sid / 2).extrude(p["hub_h"])
    pad_w, pad_t = p["chord"] * 0.45, p["pin_d"] * 3
    for k in range(p["blades"]):
        pad = (cq.Workplane("XY").box(pad_t, pad_w, p["hub_h"], centered=(False, True, False))
               .faces(">X").workplane().pushPoints([(0, p["hub_h"] / 2)]).hole(p["pin_d"])
               .rotate((0, 0, 0), (1, 0, 0), PITCH_DEG)
               .translate((sid / 2 + p["hub_wall"] - 0.3, 0, 0))
               .rotate((0, 0, 0), (0, 0, 1), 360 / p["blades"] * k))
        hub = hub.union(pad)
    return hub

def rotor_blade(p):
    """Flat-plate blade with a rounded leading edge, root tab with the hinge-pin hole."""
    L = p["rotor_d"] / 2 - p["root_cutout"]
    blade = (cq.Workplane("XY").rect(L, p["chord"], centered=(False, True)).extrude(p["blade_t"])
             .edges("|Z and >X").fillet(p["chord"] * 0.3))
    tab = (cq.Workplane("XY").center(-p["pin_d"] * 2, 0).rect(p["pin_d"] * 4, p["chord"] * 0.4)
           .extrude(p["blade_t"] * 2).faces(">Z").workplane().center(-p["pin_d"] * 0.5, 0).hole(p["pin_d"]))
    return blade.union(tab)

def water_nose(p):
    """Ogive-ish nose that slips over the bottle base, with a pocket for a mechanical timer.
    The timer releases the nose; the blades, held folded by the nose skirt, spring open."""
    sid = p["bottle_od"] + p["fit"]
    r, L, t = sid / 2 + p["nose_wall"], p["nose_len"], p["nose_wall"]
    n = 24
    outer_pts = [(r * math.sqrt(max(0.0, 1 - (L * i / n / L) ** 2)), L * i / n) for i in range(n + 1)]
    ri, Li = r - t, L - t
    inner_pts = [(ri * math.sqrt(max(0.0, 1 - (Li * i / n / Li) ** 2)), Li * i / n) for i in range(n, -1, -1)]
    shell = cq.Workplane("XZ").polyline(outer_pts + inner_pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
    outer = cq.Workplane("XZ").polyline(outer_pts + [(0, 0)]).close().revolve(360, (0, 0, 0), (0, 1, 0))
    nose = shell
    w, l, h = p["timer_bay"]
    bay = cq.Workplane("XY").workplane(offset=L * 0.25).box(w + 2 * p["wall"], l + 2 * p["wall"], h + p["wall"], centered=(True, True, False))
    pocket = cq.Workplane("XY").workplane(offset=L * 0.25 + p["wall"]).box(w, l, h, centered=(True, True, False))
    return nose.union(bay.intersect(outer)).cut(pocket)

def mass_g(part, density=PETG_G_CM3):
    return part.val().Volume() / 1000 * density

# Mass budgets the simulator assumes (sim/lineup.py and rotor_bem.py), grams
BUDGET = {"dewdrop_ring_tail": 40, "dewdrop_rotor_hub": 12, "dewdrop_rotor_blade": 6, "dewdrop_nose_timer_bay": 30,
          "seedling_ring_tail": 8, "seedling_rotor_hub": 4, "seedling_rotor_blade": 2,
          "maplewing1_ring_tail": 250, "maplewing1_rotor_hub": 60, "maplewing1_rotor_blade": 30}

def main():
    (OUT / "stl").mkdir(exist_ok=True)
    W, S, M1 = WATER, SEEDLING, MAPLEWING1
    parts = {
        "dewdrop_ring_tail": (ring_tail(W, W["bottle_od"]), 1, "TAIL-W-ring"),
        "dewdrop_rotor_hub": (rotor_hub(W, W["bottle_od"]), 1, "RB-W"),
        "dewdrop_rotor_blade": (rotor_blade(W), W["blades"], "RB-W", BALSA_G_CM3),
        "dewdrop_nose_timer_bay": (water_nose(W), 1, "NC-W"),
        "seedling_ring_tail": (ring_tail(S, S["tube_od"]), 1, "TAIL-BT50-ring"),
        "seedling_rotor_hub": (rotor_hub(S, S["tube_od"]), 1, "RB-BT50"),
        "seedling_rotor_blade": (rotor_blade(S), S["blades"], "RB-BT50", BALSA_G_CM3),
        "maplewing1_ring_tail": (ring_tail(M1, M1["tube_od"]), 1, "TAIL-54-ring"),
        "maplewing1_rotor_hub": (rotor_hub(M1, M1["tube_od"]), 1, "RB-54"),
        "maplewing1_rotor_blade": (rotor_blade(M1), M1["blades"], "RB-54", BALSA_G_CM3),
    }
    report = {}
    for name, (part, qty, sid, *dens) in parts.items():
        density = dens[0] if dens else PETG_G_CM3
        cq.exporters.export(part, str(OUT / "stl" / f"{name}.stl"), tolerance=0.05, angularTolerance=0.1)
        bb = part.val().BoundingBox()
        report[name] = {"qty": qty, "shared_id": sid, "material": "balsa" if dens else "PETG", "mass_g_each": round(mass_g(part, density), 1), "budget_g": BUDGET[name],
                        "bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)]}
        r = report[name]
        print(f"{name:<26} x{qty} {r['material']:<5} {r['mass_g_each']:>6} g each (budget {r['budget_g']} g)  bbox {r['bbox_mm']}")
    json.dump({"pitch_deg": PITCH_DEG, "material": "PETG", "water": WATER, "seedling": SEEDLING, "maplewing1": MAPLEWING1, "parts": report},
              open(OUT / "parts.json", "w"), indent=1)

if __name__ == "__main__":
    main()
