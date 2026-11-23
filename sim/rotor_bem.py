#!/usr/bin/env python3
"""Maplewing blade-element rotor descent model (MIT licence).

Finds the steady autorotating descent of a passive, fixed-pitch rotor:
  1. zero net shaft torque (the rotor drives itself), and
  2. rotor thrust = weight (steady descent).

Method: blade-element theory with a uniform induced velocity. Vertical descent
near autorotation lies in the turbulent-wake state, where simple momentum
theory fails, so the induced velocity comes from the widely used empirical
curve fit in Leishman, Principles of Helicopter Aerodynamics (2nd ed., 2006):
    v_i/v_h = k + k1*x + k2*x^2 + k3*x^3 + k4*x^4,  x = V_c/v_h in [-2, 0]
    k = 1.0, k1 = -1.125, k2 = -1.372, k3 = -1.718, k4 = -0.655
COEFFICIENTS QUOTED FROM MEMORY: verify against the book before relying on them.

Airfoil: thin flat or slightly cambered plate at low Reynolds number.
Cl = a*alpha up to stall, then a crude post-stall plateau; Cd = cd0 + k*alpha^2.
All airfoil numbers are ASSUMED until drone drop tests calibrate them.
Units: SI. Pitch: positive = leading edge up relative to the rotor plane.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from scipy.optimize import brentq

G = 9.80665

@dataclass
class Rotor:
    n_blades: int
    radius: float          # tip radius (m)
    root_cutout: float     # radius where the blade starts (m)
    chord: float           # constant chord (m)
    pitch_deg: float       # fixed collective pitch (deg)
    twist_deg: float = 0.0 # root-to-tip twist (deg, negative = washout)
    a: float = 5.0         # lift-curve slope, 1/rad (ASSUMED, low-Re plate)
    cl_max: float = 0.9    # stall Cl (ASSUMED)
    cd0: float = 0.025     # profile drag at zero lift (ASSUMED)
    k_cd: float = 1.0      # induced-like profile drag growth (ASSUMED)
    blade_mass: float = 0.0  # kg per blade, for spin-load estimate

    def disc_area(self):
        return math.pi * self.radius ** 2

def airfoil(alpha, r: Rotor):
    cl = r.a * alpha
    if abs(cl) > r.cl_max:  # crude stall: hold Cl, drag climbs
        cl = math.copysign(r.cl_max, cl)
    cd = r.cd0 + r.k_cd * alpha ** 2
    return cl, cd

def vi_turbulent(V_descent, v_h):
    """Induced velocity (positive = opposing the up-flow through the disc)."""
    x = -V_descent / v_h            # climb ratio, negative in descent
    if x <= -2.0:                   # windmill-brake state: momentum theory valid
        return v_h * (-x / 2 - math.sqrt(x * x / 4 - 1))
    k = (1.0, -1.125, -1.372, -1.718, -0.655)
    return v_h * sum(c * x ** i for i, c in enumerate(k))

def loads(rotor: Rotor, V, omega, rho, weight, n=60):
    """Thrust (N, up) and driving torque (N m, + accelerates rotor)."""
    v_h = math.sqrt(weight / (2 * rho * rotor.disc_area()))
    vi = vi_turbulent(V, v_h)
    up = V - vi                     # net upward flow through the disc
    T = Q = 0.0
    dr = (rotor.radius - rotor.root_cutout) / n
    for i in range(n):
        r = rotor.root_cutout + (i + 0.5) * dr
        ut = omega * r
        phi = math.atan2(up, ut)
        frac = (r - rotor.root_cutout) / (rotor.radius - rotor.root_cutout)
        theta = math.radians(rotor.pitch_deg + rotor.twist_deg * frac)
        alpha = theta + phi
        cl, cd = airfoil(alpha, rotor)
        q = 0.5 * rho * (ut * ut + up * up) * rotor.chord * dr
        L, D = q * cl, q * cd
        T += rotor.n_blades * (L * math.cos(phi) + D * math.sin(phi))
        Q += rotor.n_blades * (L * math.sin(phi) - D * math.cos(phi)) * r
    return T, Q

def autorotation_omega(rotor, V, rho, weight):
    """Rotor speed (rad/s) where net torque is zero at descent speed V."""
    f = lambda w: loads(rotor, V, w, rho, weight)[1]
    lo, hi = 1.0, 3000.0
    # torque is positive (driving) at low rpm and negative at high rpm
    if f(lo) <= 0:
        return None  # rotor won't spin up at this pitch: stalled or too much pitch
    if f(hi) > 0:
        return None
    return brentq(f, lo, hi, xtol=1e-4)

def descent(rotor: Rotor, mass, rho=1.08):
    """Steady descent speed (m/s) and rpm. rho default ~1,300 m site."""
    W = mass * G
    def excess(V):
        w = autorotation_omega(rotor, V, rho, W)
        if w is None:
            return -W
        return loads(rotor, V, w, rho, W)[0] - W
    Vs = [0.5 + 0.25 * i for i in range(80)]
    prev = None
    for V in Vs:
        e = excess(V)
        if prev is not None and prev[1] < 0 <= e:
            Vd = brentq(excess, prev[0], V, xtol=1e-4)
            w = autorotation_omega(rotor, Vd, rho, W)
            c_eff = 2 * W / (rho * rotor.disc_area() * Vd ** 2)
            spin_load = (rotor.blade_mass * w ** 2 * (rotor.root_cutout + rotor.radius) / 2
                         if rotor.blade_mass else None)
            return {"descent_ms": Vd, "rpm": w * 60 / (2 * math.pi), "c_eff": c_eff,
                    "tip_speed_ms": w * rotor.radius,
                    "blade_root_load_N": spin_load}
        prev = (V, e)
    return None

DESIGNS = {
    # name: (rotor, descent mass kg). Geometry is first-cut, sized in Phase 0.
    "Seedling model (0.30 m)": (Rotor(3, 0.15, 0.015, 0.025, 4.0, blade_mass=0.002), 0.080),
    "Water rocket (0.44 m)": (Rotor(3, 0.22, 0.03, 0.035, 4.0, blade_mass=0.006), 0.150),
    "Sapling L1 (1.00 m)": (Rotor(3, 0.50, 0.05, 0.060, 4.0, blade_mass=0.045), 1.55),
    "Sapling L2 (1.60 m)": (Rotor(3, 0.80, 0.08, 0.090, 4.0, blade_mass=0.120), 3.85),
}

def main():
    print("design, pitch_deg, descent_ms, rpm, c_eff, tip_speed_ms, blade_root_load_N")
    for name, (rot, m) in DESIGNS.items():
        for p in (0.0, 2.0, 4.0, 6.0, 8.0):
            rot.pitch_deg = p
            d = descent(rot, m)
            if d is None:
                print(f"{name}, {p}, no autorotation")
                continue
            load = f"{d['blade_root_load_N']:.0f}" if d["blade_root_load_N"] else "-"
            print(f"{name}, {p}, {d['descent_ms']:.2f}, {d['rpm']:.0f}, {d['c_eff']:.2f}, "
                  f"{d['tip_speed_ms']:.1f}, {load}")

if __name__ == "__main__":
    main()
