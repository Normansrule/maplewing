#!/usr/bin/env python3
"""Maplewing high-altitude sim: how high can commercial certified motors go? (MIT licence)

1-D vertical flight with:
  * the 1976 US Standard Atmosphere to 86 km (the Phase 0 sim's troposphere-only density
    is wrong above 11 km),
  * a Mach-dependent drag multiplier (generic slender-rocket shape: transonic peak, falling
    supersonic) on an ASSUMED subsonic Cd,
  * one or two stages, each a real ThrustCurve.org curve (motors/motors.json), with a
    sustainer ignition delay after booster burnout.

Vertical flight with no weathercocking, no launch angle, no heating limits and no fin or
ring-tail flutter is an UPPER BOUND. Airframe masses and Cd are ASSUMED until CAD exists.
Paper study only: nothing here is a buildable design, and anything aimed above 50,000 ft
needs Tripoli Class 3 review, an FAA waiver and an export-control review before publishing.
"""
from __future__ import annotations
import math, json, pathlib
import phase0_compare as pc

G0, R_AIR, GAMMA, RE = 9.80665, 287.053, 1.4, 6.371e6

# 1976 US Standard Atmosphere (geopotential base km, base K, lapse K/km)
LAYERS = [(0, 288.15, -6.5), (11, 216.65, 0.0), (20, 216.65, 1.0), (32, 228.65, 2.8),
          (47, 270.65, 0.0), (51, 270.65, -2.8), (71, 214.65, -2.0), (84.852, 186.87, 0.0)]

def _base_pressures():
    P = [101325.0]
    for (h0, T0, L), (h1, _, _) in zip(LAYERS, LAYERS[1:]):
        dh = (h1 - h0) * 1000
        if L == 0:
            P.append(P[-1] * math.exp(-G0 * dh / (R_AIR * T0)))
        else:
            T1 = T0 + L / 1000 * dh
            P.append(P[-1] * (T1 / T0) ** (-G0 / (R_AIR * L / 1000)))
    return P
PBASE = _base_pressures()

def atmos(z: float):
    """(density kg/m^3, speed of sound m/s) at geometric altitude z (m). Zero density above 86 km."""
    if z > 86000:
        return 0.0, 275.0
    h = RE * z / (RE + z) / 1000  # geopotential km
    i = max(k for k, L in enumerate(LAYERS) if L[0] <= h)
    h0, T0, L = LAYERS[i]
    T = T0 + L * (h - h0)
    P = PBASE[i] * (math.exp(-G0 * (h - h0) * 1000 / (R_AIR * T0)) if L == 0 else (T / T0) ** (-G0 / (R_AIR * L / 1000)))
    return P / (R_AIR * T), math.sqrt(GAMMA * R_AIR * T)

MACH_CD = [(0, 1.0), (0.8, 1.0), (1.05, 1.65), (1.3, 1.55), (2.0, 1.15), (3.0, 0.95), (5.0, 0.8), (8.0, 0.75)]
def cd_mult(M: float) -> float:
    for (m0, c0), (m1, c1) in zip(MACH_CD, MACH_CD[1:]):
        if M <= m1:
            return c0 + (c1 - c0) * (M - m0) / (m1 - m0)
    return MACH_CD[-1][1]

def impulse(m):
    return sum((t1 - t0) * (f0 + f1) / 2 for (t0, f0), (t1, f1) in zip(m.curve, m.curve[1:]))

def fly(stages, site_alt=1190.0, dt=0.005, delay=2.0):
    """stages: list from bottom to top of dict(motor, dry, d, cd). Upper stages ride along until
    the stage below burns out; each upper stage lights `delay` s after the one below burns out.
    Spent stages drop off at the next ignition (no drag credit for separation)."""
    t = h = v = 0.0
    k, t_ign = 0, 0.0
    vmax = qmax = Mmax = 0.0
    log = {}
    while True:
        live = stages[k:]
        m_mot = live[0]["motor"].mass(t - t_ign) if t >= t_ign else live[0]["motor"].total_mass
        m = sum(s["dry"] for s in live) + m_mot + sum(s["motor"].total_mass for s in live[1:])
        F = live[0]["motor"].thrust(t - t_ign) if t >= t_ign else 0.0
        rho, a = atmos(site_alt + h)
        M = abs(v) / a
        d = max(s["d"] for s in live)
        A = math.pi * d * d / 4
        q = 0.5 * rho * v * v
        D = q * live[0]["cd"] * cd_mult(M) * A * (1 if v >= 0 else -1)
        g = G0 * (RE / (RE + site_alt + h)) ** 2
        acc = (F - D) / m - g
        if h <= 0 and acc < 0:
            acc = 0.0
        v += acc * dt; h += v * dt; t += dt
        vmax, qmax, Mmax = max(vmax, v), max(qmax, q), max(Mmax, M)
        burnout = t - t_ign > live[0]["motor"].burn_time
        if burnout and f"burnout{k}" not in log:
            log[f"burnout{k}"] = {"t": round(t, 1), "h_km": round(h / 1000, 2), "v": round(v), "mach": round(M, 2)}
        if burnout and len(live) > 1 and t - t_ign > live[0]["motor"].burn_time + delay:
            k += 1; t_ign = t
        if v < 0 and burnout and len(stages[k:]) == 1:
            break
    return {"apogee_km": round(h / 1000, 1), "apogee_ft": round(h * 3.281), "t_apogee_s": round(t),
            "vmax_ms": round(vmax), "mach_max": round(Mmax, 2), "qmax_kPa": round(qmax / 1000),
            "total_impulse_Ns": round(sum(impulse(s["motor"]) for s in stages)), **log}

M = pc.load_motor
def lineup():
    """ASSUMED airframes. Ring-tail Cd = fin Cd x 1.35 (Phase 0 ring/fin ratio)."""
    N5600 = M("N5600", "Cesaroni N5600 (98 mm)")
    O5500 = M("O5500X", "AeroTech O5500X (98 mm)")
    out = {}
    for tail, k in (("fins", 1.0), ("ring", 1.35)):
        out[f"Emergent-1 single stage, N5600, {tail}"] = [dict(motor=N5600, dry=4.5, d=0.102, cd=0.45 * k)]
        out[f"Emergent-2 two stage O5500X + N5600, {tail} (Class 2)"] = [
            dict(motor=O5500, dry=3.5, d=0.102, cd=0.45 * k), dict(motor=N5600, dry=4.5, d=0.102, cd=0.40 * k)]
    return out

def main():
    res = {}
    for name, st in lineup().items():
        r = fly(st); res[name] = r
        print(f"{name:<52} {r['apogee_km']:>6.1f} km {r['apogee_ft']:>8} ft  Mach {r['mach_max']:>4.1f}  q {r['qmax_kPa']:>4} kPa  I {r['total_impulse_Ns']}")
    json.dump(res, open(pathlib.Path(__file__).with_name("high_altitude.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
