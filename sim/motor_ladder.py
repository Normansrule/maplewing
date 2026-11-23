#!/usr/bin/env python3
"""Maplewing motor ladder (MIT licence).

A tiered list of COMMERCIAL CERTIFIED motors (plus water-rocket pressure tiers) that an
individual can buy, from no certification up to HPR Level 2. Every rung is flown in the
1-D simulator with its real ThrustCurve.org curve (motors/motors.json) in a reference
ring-tail airframe, and checked against the rule-of-thumb launch-safety numbers.

Never: motor making, propellant, "research" motors, or modified motors. Buying a motor
is the builder's decision; prices and rules in LADDER are as checked on 2026-11-04 and must be
re-verified at nar.org / tripoli.org / the vendor before any purchase.

Run: python3 motor_ladder.py            -> table + motor_ladder.json
"""
from __future__ import annotations
import json, math, pathlib
import phase0_compare as pc

HERE = pathlib.Path(__file__).resolve().parent

# ------------------------------------------------------------------ rule thresholds
# Model-rocket motor limits (NFPA 1122/1125 via NAR; secondhand, VERIFY at nar.org, which is
# blocked from this cloud session): a single motor above any of these is a high-power motor.
MODEL_MAX_PROP_KG = 0.0625      # 62.5 g propellant
MODEL_MAX_IMPULSE = 160.0       # N·s (G class upper bound)
MODEL_MAX_AVG_THRUST = 80.0     # N
# Rules of thumb used by clubs and kit makers (not code text): VERIFY with the RSO.
MIN_THRUST_TO_WEIGHT = 5.0
MIN_RAIL_EXIT_MS = 15.0

def impulse_class(I: float) -> str:
    """NAR letter class: A = 1.26–2.5 N·s, each letter doubles."""
    letters, hi = "ABCDEFGHIJKLMNO", 2.5
    for L in letters:
        if I <= hi + 1e-9:
            return L
        hi *= 2
    return "?"

# ------------------------------------------------------------------ reference airframes
# Seedling-29: ASSUMED BT-60-class (41.6 mm) ring-tail mid-power airframe for the 24/29 mm
# rungs, until CAD and a weighed build replace it. The other airframes come from phase0_compare.
def seedling29(motor):
    return pc.Rocket(f"Seedling-29 ring (ASSUMED), {motor.name}", 0.0416, 0.14, 0.80, 0.230, 0.42,
                     motor, 0.74, cd=0.70, tail={"type": "ring", "D_ring": 0.090, "c": 0.060, "xf": 0.735},
                     rail_len=0.9)

D = {r.name: r for r in pc.designs()}
def with_motor(base_name, motor):
    r = D[base_name]
    return pc.Rocket(f"{base_name}, {motor.name}", r.d, r.L_nose, r.L_total, r.dry_mass, r.cg_dry, motor,
                     r.motor_cg, r.cd, r.tail, r.rail_len)

M = lambda k, n: pc.load_motor(k, n)

# rung, who can buy, price note (USD, as checked 2026-11-04), motor key/name, airframe factory
LADDER = [
    # rung 1: 18 mm black powder, no certification (Estes kits/motors at hobby and big-box stores)
    (1, "Anyone, no certification (check local and state rules)", "Estes C6-5 3-pack about $14–16 at retailers; bulk 24-pack about $110",
     ("A8", "Estes A8-3"), lambda m: with_motor("Seedling model, ring tail", m)),
    (1, "Anyone, no certification", "Estes B6-4 packs at retailers (verify)", ("B6", "Estes B6-4"),
     lambda m: with_motor("Seedling model, ring tail", m)),
    (1, "Anyone, no certification", "Estes C6-5 3-pack about $14–16", ("C6", "Estes C6-5"),
     lambda m: with_motor("Seedling model, ring tail", m)),
    # rung 2: 24 mm D, still model rocketry
    (2, "Anyone, no certification", "Estes D12-5 packs at retailers (verify)", ("D12", "Estes D12-5"), seedling29),
    # rung 3: 29 mm E/F black powder (Estes); adult purchase for some sellers (verify)
    (3, "No certification; some sellers require 18+ for E/F (verify)", "Estes E16 / F26 packs (verify)",
     ("E16", "Estes E16-6"), seedling29),
    (3, "No certification; adult purchase typical (verify)", "Estes F26 (AeroTech-made F26FJ) (verify)",
     ("F26", "Estes F26-6"), seedling29),
    # rung 4: 29 mm composite G single-use, still a model-rocket motor by the limits above
    (4, "No HPR certification; G motors sold to adults 18+ (Estes guidance)", "AeroTech G40W single-use (verify price); ships US mail per vendor for some G motors",
     ("G40W", "AeroTech G40W-7"), seedling29),
    # rung 5: HPR Level 1 (H/I) — NAR or TRA L1, 18+, member, one certification flight
    (5, "NAR or TRA Level 1, 18+ (vendor ships after proof of age and L1)", "AeroTech H128W-14A RMS-29/180 reload $39.49 at aerotech-rocketry.com; needs RMS-29/180 hardware (verify) and hazmat ground shipping",
     ("H128W", "AeroTech H128W-14A"), lambda m: with_motor("Sapling L1, ring tail", m)),
    # rung 6: HPR Level 2 (J/K/L) — L1 + written exam + J/K/L certification flight
    (6, "NAR or TRA Level 2: L1 + written exam + J/K/L flight, 18+", "AeroTech J350W reload (verify price) + RMS-38/720 hardware (verify)",
     ("J350W", "AeroTech J350W-14A"), lambda m: with_motor("Sapling L2, ring tail", m)),
]

# Water-rocket rung 0: pressure tiers, 2 L PET only, remote release.
# NASA Glenn classroom guidance: about 50 psi typical, never above 90 psi; reported bursts 120–168 psi
# (forum data); retire bottles after 10–15 launches. Maplewing rule: operate <= 60 psi only after
# each bottle passes a WATER-filled (hydrostatic) proof test at 1.5x = 90 psi.
WATER_TIERS_PSI = (40, 50, 60)
WATER_PROOF_FACTOR = 1.5

def motor_row(m: pc.Motor):
    I = m.cum[-1] if hasattr(m, "cum") else None
    if I is None:
        I = sum((t1 - t0) * (f0 + f1) / 2 for (t0, f0), (t1, f1) in zip(m.curve, m.curve[1:]))
    avg = I / m.burn_time
    peak = max(f for _, f in m.curve)
    hpr = m.prop_mass > MODEL_MAX_PROP_KG + 1e-6 or I > MODEL_MAX_IMPULSE or avg > MODEL_MAX_AVG_THRUST
    return I, avg, peak, hpr

def main():
    rows = []
    for psi in WATER_TIERS_PSI:
        w = pc.water_rocket(P_gauge_psi=psi)
        rows.append({"rung": 0, "motor": f"Water, 2 L PET at {psi} psi", "class": "water",
                     "buy": "Anyone", "price": "Bottle free; pump with gauge and remote release (verify)",
                     "proof_test_psi": psi * WATER_PROOF_FACTOR, "apogee_m": round(w["apogee_m"], 1),
                     "vmax_ms": round(w["vmax_ms"], 1), "airframe": "Phase 0 water rocket (ASSUMED 150 g dry)"})
    for rung, buy, price, (key, name), frame in LADDER:
        m = M(key, name)
        r = frame(m)
        I, avg, peak, hpr = motor_row(m)
        f = r.fly(); s = r.stability()
        tw = avg / (s["liftoff_mass_kg"] * pc.G)
        flags = []
        if tw < MIN_THRUST_TO_WEIGHT: flags.append(f"avg T/W {tw:.1f} < {MIN_THRUST_TO_WEIGHT:.0f}")
        if f["v_rail_ms"] < MIN_RAIL_EXIT_MS: flags.append(f"rail exit {f['v_rail_ms']:.1f} m/s < {MIN_RAIL_EXIT_MS:.0f}")
        if s["margin_cal"] < 1.0: flags.append(f"margin {s['margin_cal']:.2f} cal < 1")
        rows.append({"rung": rung, "motor": name, "class": impulse_class(I), "impulse_Ns": round(I, 1),
                     "avg_thrust_N": round(avg, 1), "peak_thrust_N": round(peak, 1),
                     "prop_g": round(m.prop_mass * 1000, 1), "hpr": hpr, "buy": buy, "price": price,
                     "airframe": r.name.split(",")[0], "liftoff_kg": round(s["liftoff_mass_kg"], 3),
                     "margin_cal": round(s["margin_cal"], 2), "apogee_m": round(f["apogee_m"], 1),
                     "vmax_ms": round(f["vmax_ms"], 1), "v_rail_ms": round(f["v_rail_ms"], 1),
                     "thrust_to_weight": round(tw, 1), "flags": flags, "curve": m.source})
    json.dump({"site_alt_m": 1300, "rows": rows}, open(HERE / "motor_ladder.json", "w"), indent=1)
    print(f"{'R':>1} {'Motor':<26}{'Cl':>3}{'I N·s':>7}{'avgN':>6}{'prop g':>7}{'HPR':>5}{'kg':>7}{'cal':>6}{'apo m':>7}{'rail':>6}{'T/W':>5}  flags")
    for x in rows:
        if x["class"] == "water":
            print(f"0 {x['motor']:<26}{'-':>3}{'':>7}{'':>6}{'':>7}{'':>5}{'':>7}{'':>6}{x['apogee_m']:>7.0f}{'':>6}{'':>5}  proof {x['proof_test_psi']:.0f} psi")
            continue
        print(f"{x['rung']} {x['motor']:<26}{x['class']:>3}{x['impulse_Ns']:>7.1f}{x['avg_thrust_N']:>6.1f}{x['prop_g']:>7.1f}"
              f"{'yes' if x['hpr'] else 'no':>5}{x['liftoff_kg']:>7.3f}{x['margin_cal']:>6.2f}{x['apogee_m']:>7.0f}{x['v_rail_ms']:>6.1f}{x['thrust_to_weight']:>5.1f}  {'; '.join(x['flags'])}")

if __name__ == "__main__":
    main()
