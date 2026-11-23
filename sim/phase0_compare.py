#!/usr/bin/env python3
"""Maplewing Phase 0 first comparison (MIT licence).

1. Static stability: extended Barrowman for nose + planar fins, and a ring tail
   modelled as an "equivalent planar fin set" (same developed area, same radial
   reach). That ring model is a community workaround, not a validated method:
   https://rocketryforum.com/threads/an-experiment-with-ring-tail-simulation-in-openrocket.187126
   so we also report the margin with the ring's normal-force slope at -30 %.
2. Apogee: 1-D vertical flight (RK4), standard-atmosphere density, real
   ThrustCurve.org thrust curves (motors/*.eng, linear interpolation).
3. Descent: parachute v = sqrt(2mg / (rho*Cd*A)) vs autorotating rotor with an
   effective disc drag coefficient (NAR helicopter-duration note: a good rotor
   reaches ~85 % of a round parachute's Cd; best case v ~ 3.6*sqrt(m/S)).

Every number marked ASSUMED is a placeholder until OpenRocket, RocketPy, CFD,
swing tests or drop tests replace it. Units: SI.
"""
from __future__ import annotations
import math, json, sys
from dataclasses import dataclass, field

G = 9.80665

def rho(h: float) -> float:
    """ISA troposphere density (kg/m^3) at geometric altitude h (m) above sea level."""
    T = 288.15 - 0.0065 * h
    return 1.225 * (T / 288.15) ** 4.2559

# ---------------------------------------------------------------- motors
MOTOR_DIR = __import__("pathlib").Path(__file__).resolve().parent / "motors"

def read_eng(path) -> list[tuple[float, float]]:
    """RASP .eng thrust points [(t s, F N)], with the implicit (0, 0) start added."""
    pts, header = [(0.0, 0.0)], False
    for line in open(path, encoding="latin-1"):
        line = line.split(";")[0].strip()
        if not line:
            continue
        if not header:          # first non-comment line: name dia len delays prop total mfr
            header = True
            continue
        t, f = map(float, line.split()[:2])
        if t > pts[-1][0]:
            pts.append((t, f))
    return pts

@dataclass
class Motor:
    """Commercial certified motor: ThrustCurve.org .eng curve + certification-record masses."""
    name: str
    curve: list            # [(t, F)] from the .eng file
    prop_mass: float       # kg (ThrustCurve motor record)
    total_mass: float      # kg (ThrustCurve motor record)
    source: str = ""

    def __post_init__(self):
        self.burn_time = self.curve[-1][0]
        cum = [0.0]                                     # impulse burned, trapezoid rule
        for (t0, f0), (t1, f1) in zip(self.curve, self.curve[1:]):
            cum.append(cum[-1] + (t1 - t0) * (f0 + f1) / 2)
        self._cum = cum
        self.total_impulse = cum[-1]

    def _seg(self, t):
        c = self.curve
        lo, hi = 0, len(c) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if c[mid][0] <= t: lo = mid
            else: hi = mid
        return lo

    def thrust(self, t: float) -> float:
        """Linear interpolation between .eng points (what OpenRocket and RocketPy do)."""
        if t <= 0 or t >= self.burn_time:
            return 0.0
        i = self._seg(t)
        (t0, f0), (t1, f1) = self.curve[i], self.curve[i + 1]
        return f0 + (f1 - f0) * (t - t0) / (t1 - t0)

    def mass(self, t: float) -> float:
        """Propellant burns in proportion to impulse delivered (OpenRocket's assumption)."""
        if t <= 0:
            return self.total_mass
        if t >= self.burn_time:
            return self.total_mass - self.prop_mass
        i = self._seg(t)
        t0, f0 = self.curve[i]
        burned = self._cum[i] + (t - t0) * (f0 + self.thrust(t)) / 2
        return self.total_mass - self.prop_mass * burned / self.total_impulse

def load_motor(key: str, name: str) -> Motor:
    meta = json.load(open(MOTOR_DIR / "motors.json"))["motors"][key]
    rec = meta["record"]
    return Motor(name, read_eng(MOTOR_DIR / meta["eng"]), rec["prop_mass_kg"], rec["total_mass_kg"],
                 meta["simfile_page"])

# Real thrust curves from ThrustCurve.org (sources and licences in motors/motors.json).
# A delay number does not change the thrust curve, only the ejection time.
A8_3 = load_motor("A8", "Estes A8-3")
B6_4 = load_motor("B6", "Estes B6-4")
C6_5 = load_motor("C6", "Estes C6-5")
D12_5 = load_motor("D12", "Estes D12-5")
H128W = load_motor("H128W", "AeroTech H128W-14A")
J350W = load_motor("J350W", "AeroTech J350W-14A")

# ---------------------------------------------------------------- Barrowman
def nose_cna(kind="ogive") -> float:
    return 2.0

def nose_xcp(L: float, kind="ogive") -> float:
    return {"ogive": 0.466, "cone": 0.666, "vk": 0.500}[kind] * L

def fins_cna(N: float, s: float, cr: float, ct: float, xs: float, d: float) -> float:
    """Barrowman fin normal-force slope incl. body interference. xs = sweep length."""
    lf = math.sqrt(s ** 2 + (xs + ct / 2 - cr / 2) ** 2)  # mid-chord line length
    cna = (4 * N * (s / d) ** 2) / (1 + math.sqrt(1 + (2 * lf / (cr + ct)) ** 2))
    r = d / 2
    return cna * (1 + r / (s + r))

def fins_xcp(xf: float, s: float, cr: float, ct: float, xs: float) -> float:
    """xf = distance from nose tip to fin root leading edge."""
    return xf + xs * (cr + 2 * ct) / (3 * (cr + ct)) + (cr + ct - cr * ct / (cr + ct)) / 6

@dataclass
class Rocket:
    name: str
    d: float              # body diameter (m)
    L_nose: float
    L_total: float
    dry_mass: float       # without motor (kg)
    cg_dry: float         # from nose tip (m)
    motor: Motor
    motor_cg: float       # from nose tip (m)
    cd: float             # ASSUMED zero-lift drag coefficient (ref = body area)
    tail: dict = field(default_factory=dict)
    rail_len: float = 1.0
    recovery_mass_frac: float = 1.0

    def tail_cna_xcp(self, ring_factor=1.0):
        t = self.tail
        if t["type"] == "fins":
            return (fins_cna(t["N"], t["s"], t["cr"], t["ct"], t["xs"], self.d),
                    fins_xcp(t["xf"], t["s"], t["cr"], t["ct"], t["xs"]))
        # ring tail -> equivalent planar fin set (community method, unvalidated)
        Dm = t["D_ring"]                       # ring mean diameter
        h = (Dm - self.d) / 2                  # radial standoff of the ring
        N_eq = math.pi * Dm / h                # developed circumference / standoff
        # cos^2 averaging around the ring is already inside Barrowman's N-scaling,
        # so N_eq panels of span h and chord c have the ring's developed area.
        cna = fins_cna(N_eq, h, t["c"], t["c"], 0.0, self.d) * ring_factor
        # struts add a little; ignored (conservative for CP)
        return cna, fins_xcp(t["xf"], h, t["c"], t["c"], 0.0)

    def stability(self, ring_factor=1.0):
        cn_n, x_n = nose_cna(), nose_xcp(self.L_nose)
        cn_t, x_t = self.tail_cna_xcp(ring_factor)
        cp = (cn_n * x_n + cn_t * x_t) / (cn_n + cn_t)
        m = self.dry_mass + self.motor.total_mass
        cg = (self.dry_mass * self.cg_dry + self.motor.total_mass * self.motor_cg) / m
        return {"cp_m": cp, "cg_m": cg, "margin_cal": (cp - cg) / self.d,
                "liftoff_mass_kg": m}

    def fly(self, h0=1300.0, dt=0.002):
        """1-D vertical ascent from launch-site altitude h0 (m ASL). Returns metrics."""
        A = math.pi * self.d ** 2 / 4
        t, h, v = 0.0, 0.0, 0.0
        vmax, v_rail = 0.0, None

        def acc(t, h, v):
            m = self.dry_mass + self.motor.mass(t)
            F = self.motor.thrust(t)
            D = 0.5 * rho(h0 + h) * v * abs(v) * self.cd * A
            a = (F - D) / m - G
            if h <= 0 and a < 0 and t < self.motor.burn_time:
                return 0.0
            return a

        while True:
            k1v = acc(t, h, v); k1h = v
            k2v = acc(t + dt/2, h + k1h*dt/2, v + k1v*dt/2); k2h = v + k1v*dt/2
            k3v = acc(t + dt/2, h + k2h*dt/2, v + k2v*dt/2); k3h = v + k2v*dt/2
            k4v = acc(t + dt, h + k3h*dt, v + k3v*dt); k4h = v + k3v*dt
            v += dt * (k1v + 2*k2v + 2*k3v + k4v) / 6
            h += dt * (k1h + 2*k2h + 2*k3h + k4h) / 6
            t += dt
            vmax = max(vmax, v)
            if v_rail is None and h >= self.rail_len:
                v_rail = v
            if t > self.motor.burn_time and v <= 0:
                break
        return {"apogee_m": h, "t_apogee_s": t, "vmax_ms": vmax,
                "v_rail_ms": v_rail or 0.0, "mach_max": vmax / 340.0}

# ---------------------------------------------------------------- descent
def v_parachute(m, diameter, cd=1.5, h=1300.0):
    A = math.pi * diameter ** 2 / 4
    return math.sqrt(2 * m * G / (rho(h) * cd * A))

def v_rotor(m, rotor_diameter, c_eff=1.0, h=1300.0):
    """Autorotation as an equivalent drag disc. c_eff ASSUMED 0.8-1.25
    (NAR note: ideal ~1.24, good real rotors ~0.85 x round-chute Cd)."""
    S = math.pi * rotor_diameter ** 2 / 4
    return math.sqrt(2 * m * G / (rho(h) * c_eff * S))

def ke(m, v):
    return 0.5 * m * v * v

# ---------------------------------------------------------------- water rocket
def water_rocket(P_gauge_psi=60, V_bottle=0.002, V_water=0.0006, d_noz=0.0217,
                 dry=0.150, d_body=0.105, cd=0.55, gamma=1.4, dt=1e-4):
    Pa = 101325.0
    P0 = Pa + P_gauge_psi * 6894.76
    An = math.pi * d_noz ** 2 / 4
    A = math.pi * d_body ** 2 / 4
    Va0 = V_bottle - V_water
    mw = V_water * 1000.0
    rho_air0 = P0 / (287.0 * 293.0)
    m_air = rho_air0 * Va0
    t = h = v = 0.0
    vmax = 0.0
    # water phase
    while mw > 0:
        Va = V_bottle - mw / 1000.0
        P = P0 * (Va0 / Va) ** gamma
        if P <= Pa:
            break
        ve = math.sqrt(2 * (P - Pa) / 1000.0)
        mdot = 1000.0 * An * ve
        F = mdot * ve
        m = dry + mw + m_air
        a = (F - 0.5 * rho(h) * v * abs(v) * cd * A) / m - G
        v += a * dt; h += v * dt; t += dt
        mw -= mdot * dt
        vmax = max(vmax, v)
    # air pulse (choked/unchoked, isentropic blowdown, simplified)
    P = P0 * (Va0 / V_bottle) ** gamma
    T = 293.0 * (P / P0) ** ((gamma - 1) / gamma)
    while P > Pa * 1.01:
        rho_a = m_air / V_bottle
        if P / Pa > 1.893:
            mdot = An * P * math.sqrt(gamma / (287 * T)) * (2 / (gamma + 1)) ** ((gamma + 1) / (2 * (gamma - 1)))
            Te = T * 2 / (gamma + 1); ve = math.sqrt(gamma * 287 * Te)
            Pe = P * (2 / (gamma + 1)) ** (gamma / (gamma - 1))
            F = mdot * ve + (Pe - Pa) * An
        else:
            ve = math.sqrt(2 * (P - Pa) / rho_a); mdot = rho_a * An * ve; F = mdot * ve
        m = dry + m_air
        a = (F - 0.5 * rho(h) * v * abs(v) * cd * A) / m - G
        v += a * dt; h += v * dt; t += dt
        m_air -= mdot * dt
        P = P * (m_air / (m_air + mdot * dt)) ** gamma
        T = T * (m_air / (m_air + mdot * dt)) ** (gamma - 1)
        vmax = max(vmax, v)
    # coast
    while v > 0:
        a = -G - 0.5 * rho(h) * v * abs(v) * cd * A / dry
        v += a * dt; h += v * dt; t += dt
    return {"apogee_m": h, "vmax_ms": vmax, "t_apogee_s": t}

# ---------------------------------------------------------------- designs
def designs():
    d50 = 0.0248  # Estes BT-50 class OD (the Roto Rocket is 0.98 in)
    fins_model = Rocket("Seedling model, 3 fins", d50, 0.10, 0.55, 0.062, 0.31, C6_5, 0.50, cd=0.50,
                        tail={"type": "fins", "N": 3, "s": 0.035, "cr": 0.055, "ct": 0.028, "xs": 0.025, "xf": 0.495},
                        rail_len=0.9)
    ring_model = Rocket("Seedling model, ring tail", d50, 0.10, 0.55, 0.068, 0.32, C6_5, 0.50, cd=0.70,
                        tail={"type": "ring", "D_ring": 0.055, "c": 0.040, "xf": 0.505}, rail_len=0.9)
    l1_fins = Rocket("Sapling L1, 3 fins", 0.0574, 0.25, 1.25, 1.30, 0.70, H128W, 1.15, cd=0.48,
                     tail={"type": "fins", "N": 3, "s": 0.060, "cr": 0.140, "ct": 0.055, "xs": 0.075, "xf": 1.10},
                     rail_len=1.83)
    l1_ring = Rocket("Sapling L1, ring tail", 0.0574, 0.25, 1.25, 1.42, 0.72, H128W, 1.15, cd=0.65,
                     tail={"type": "ring", "D_ring": 0.120, "c": 0.100, "xf": 1.14}, rail_len=1.83)
    l2_ring = Rocket("Sapling L2, ring tail", 0.1016, 0.40, 1.95, 3.60, 1.10, J350W, 1.76, cd=0.62,
                     tail={"type": "ring", "D_ring": 0.205, "c": 0.160, "xf": 1.78}, rail_len=2.44)
    # Taproot: traditional finned rocket, Estes Alpha III class (24.8 mm x 307 mm, 34 g, published).
    # Fin geometry and CG are ASSUMED until a kit is measured.
    taproot = [Rocket(f"Taproot (Alpha III class), 3 fins, {m.name}", d50, 0.075, 0.307, 0.034, 0.165, m, 0.27, cd=0.643,  # Cd calibrated: matches Estes published 351 m on C6-5 at sea level with the ThrustCurve.org C6 curve (was 0.75 with the old 10 N·s curve)
                      tail={"type": "fins", "N": 3, "s": 0.045, "cr": 0.060, "ct": 0.025, "xs": 0.040, "xf": 0.245},
                      rail_len=0.9) for m in (A8_3, B6_4, C6_5)]
    return [fins_model, ring_model, l1_fins, l1_ring, l2_ring] + taproot

def main():
    out = {"rockets": [], "descent": [], "water": None}
    for r in designs():
        s = r.stability()
        row = {"name": r.name, "motor": r.motor.name, **{k: round(v, 3) for k, v in s.items()},
               **{k: round(v, 2) for k, v in r.fly().items()}, "cd_assumed": r.cd}
        if r.tail["type"] == "ring":
            row["margin_cal_ring_minus30pct"] = round(r.stability(0.7)["margin_cal"], 2)
        out["rockets"].append(row)
    # descent comparisons: (label, descent mass kg, chute D m, rotor D m)
    for label, m, chute, rotor in [("Taproot (C6 spent)", 0.046, 0.305, 0.0),
                                   ("Water rocket", 0.150, 0.45, 0.44),
                                   ("Seedling model (C6 spent)", 0.080, 0.30, 0.30),
                                   ("Sapling L1 (H128W spent)", 1.55, 0.91, 1.00),
                                   ("Sapling L2 (J350W spent)", 3.85, 1.52, 1.60)]:
        vp = v_parachute(m, chute)
        if rotor == 0:
            out["descent"].append({"vehicle": label, "mass_kg": m, "chute_D_m": chute,
                                   "v_chute_ms": round(vp, 2), "ke_chute_J": round(ke(m, vp), 2)})
            continue
        vr = [v_rotor(m, rotor, c) for c in (0.8, 1.0, 1.25)]
        out["descent"].append({"vehicle": label, "mass_kg": m, "chute_D_m": chute,
                               "v_chute_ms": round(vp, 2), "rotor_D_m": rotor,
                               "v_rotor_ms_ceff_0.8": round(vr[0], 2), "v_rotor_ms_ceff_1.0": round(vr[1], 2),
                               "v_rotor_ms_ceff_1.25": round(vr[2], 2),
                               "ke_chute_J": round(ke(m, vp), 1), "ke_rotor_J_ceff1": round(ke(m, vr[1]), 1)})
    out["water"] = {k: round(v, 2) for k, v in water_rocket().items()}
    out["water"]["setup"] = "2 L PET, 60 psi gauge, 0.6 L water, 21.7 mm neck, 150 g dry, Cd 0.55 ASSUMED"
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
