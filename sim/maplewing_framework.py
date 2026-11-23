#!/usr/bin/env python3
"""Maplewing shared framework: one module/stage/vehicle type system for all five rockets (MIT licence).

Every rocket is a stack of Stages (bottom to top). Every Stage is built from shared Modules
(nose, avionics bay, rotor bay, chute bay, ring tail or fins, interstage, motor mount) and
carries its OWN passive Landing system, so each piece that separates comes down on its own.

The project's hard scope rules are encoded as checks (validate()), so a design that breaks
them fails loudly instead of quietly reaching a configurator, a BOM or a range:
  * certified commercial motors only (must exist in motors/motors.json with a cert_org)
  * passive only: no guidance, TVC, canards, servos or actively controlled rotor pitch
  * every stage has a landing system; rotors are fixed pitch
  * upper stages lit only by commercial altimeters with altitude/tilt/time inhibits (no timers
    alone, no motor-ejection staging, no DIY firing circuits)
  * HPR stages deploy with redundant commercial altimeters and keep a backup parachute
  * water rockets: PET bottle, <= 60 psi, 1.5x hydrostatic proof, remote release

FAA class (14 CFR 101.22) and NAR/TRA certification level are COMPUTED, not declared, because
they are different things: an H-motor rocket under 1,500 g with <= 125 g propellant and no
metal is FAA Class 1 but still needs Level 1 to buy and fly the H motor.

All masses, Cd values and ring-tail factors are ASSUMED until CAD, weighing and tests replace them.
"""
from __future__ import annotations
import json, math, pathlib
from dataclasses import replace, dataclass, field, asdict
import phase0_compare as pc
import high_altitude as ha

HERE = pathlib.Path(__file__).resolve().parent
MOTORS = json.load(open(HERE / "motors" / "motors.json"))["motors"]

# ------------------------------------------------------------------ rule constants
FAA_C1_MAX_PROP_KG, FAA_C1_MAX_MASS_KG = 0.125, 1.500        # 14 CFR 101.22(a)
FAA_C2_MAX_IMPULSE = 40960.0                                  # 14 CFR 101.22(b)
FAA_AMATEUR_MAX_IMPULSE, FAA_AMATEUR_MAX_ALT_KM = 889600.0, 150.0  # 14 CFR 1.1
NFPA_MODEL_MOTOR = dict(prop_kg=0.0625, impulse=160.0, avg_thrust=80.0)  # secondhand, VERIFY at nar.org
LANDING_TARGET_MS = 6.5        # rule-of-thumb main descent rate; VERIFY with the RSO
WATER_MAX_PSI, WATER_PROOF = 60, 1.5
FORBIDDEN_MODULES = {"guidance", "tvc", "canard", "servo", "active_rotor", "steerable_fin", "pyro_diy"}
STAGING_INHIBITS = {"altitude", "tilt", "time"}
ROTOR_C_EFF, CHUTE_CD = 1.08, 1.5   # rotor from rotor_bem.py at 6 deg; round chute typical

# ------------------------------------------------------------------ types
@dataclass
class Module:
    kind: str                 # nose | avbay | rotor_bay | chute_bay | ring_tail | fins | interstage | motor_mount | body | bottle
    mass: float               # kg, ASSUMED until weighed
    shared_id: str = ""       # same id = the same physical design reused across rockets
    reusable: bool = True
    metal: bool = False

@dataclass
class Landing:
    primary: str              # rotor | parachute
    backup: str | None        # parachute | None
    deploy: str               # motor_ejection | commercial_altimeter | mechanical_timer
    redundant_altimeters: bool = False
    drogue: bool = False      # drogue at apogee, main/rotor low (for high-altitude stages)
    primary_d: float = 0.0    # m; 0 = size automatically to LANDING_TARGET_MS
    backup_d: float = 0.0

@dataclass
class Stage:
    name: str
    d: float                  # body outer diameter (m)
    cd: float                 # ASSUMED subsonic Cd (body area)
    tail: str                 # ring | fins
    modules: list[Module]
    landing: Landing
    motor: str | None = None  # key into motors.json; None for water
    ignition: str = "ground"  # ground | commercial_altimeter
    inhibits: tuple = ()      # for airstarts: subset of STAGING_INHIBITS
    delay_s: float | None = None  # motor-ejection delay, must be one the motor is sold with

    @property
    def dry(self) -> float:
        return sum(m.mass for m in self.modules)

@dataclass
class Vehicle:
    name: str
    tier: str
    stages: list[Stage]
    site_alt: float = 1300.0
    staging_delay_s: float = 2.0
    water: dict | None = None  # {"psi", "water_l", "bottle"} for water rockets

# ------------------------------------------------------------------ motors and classification
_MOTOR_CACHE: dict = {}
def motor(key: str) -> pc.Motor:
    if key not in _MOTOR_CACHE:
        _MOTOR_CACHE[key] = pc.load_motor(key, key)
    return _MOTOR_CACHE[key]

def impulse(key: str) -> float:
    return ha.impulse(motor(key))

def letter(I: float) -> str:
    hi = 2.5
    for L in "ABCDEFGHIJKLMNOP":
        if I <= hi + 1e-9:
            return L
        hi *= 2
    return "?"

def is_model_motor(key: str) -> bool:
    m = motor(key); I = impulse(key)
    return (m.prop_mass <= NFPA_MODEL_MOTOR["prop_kg"] + 1e-6 and I <= NFPA_MODEL_MOTOR["impulse"]
            and I / m.burn_time <= NFPA_MODEL_MOTOR["avg_thrust"])

def liftoff_mass(v: Vehicle) -> float:
    return sum(s.dry + (motor(s.motor).total_mass if s.motor else 0.0) for s in v.stages)

def classify(v: Vehicle) -> dict:
    keys = [s.motor for s in v.stages if s.motor]
    if not keys:
        return {"faa_class": "not an FAA amateur rocket (water/air)", "cert_level": "none", "total_impulse_Ns": 0}
    I = sum(impulse(k) for k in keys)
    prop = sum(motor(k).prop_mass for k in keys)
    metal = any(m.metal for s in v.stages for m in s.modules)
    if prop <= FAA_C1_MAX_PROP_KG and liftoff_mass(v) <= FAA_C1_MAX_MASS_KG and not metal:
        faa = "Class 1 (model rocket)"
    elif I <= FAA_C2_MAX_IMPULSE:
        faa = "Class 2 (high-power)"
    elif I <= FAA_AMATEUR_MAX_IMPULSE:
        faa = "Class 3 (advanced high-power)"
    else:
        faa = "not amateur: FAA launch licence"
    worst = max(keys, key=impulse)
    L = letter(impulse(worst))
    if all(is_model_motor(k) for k in keys) and liftoff_mass(v) <= FAA_C1_MAX_MASS_KG:
        cert = "none (G and up: adult purchase)" if L == "G" else "none"
    else:
        cert = {"H": "Level 1", "I": "Level 1", "J": "Level 2", "K": "Level 2", "L": "Level 2",
                "M": "Level 3", "N": "Level 3", "O": "Level 3"}.get(L, "Level 1 (HPR by mass/thrust)")
    return {"faa_class": faa, "cert_level": cert, "total_impulse_Ns": round(I),
            "propellant_kg": round(prop, 3), "largest_motor": f"{worst} ({L})"}

# ------------------------------------------------------------------ scope rules
def validate(v: Vehicle) -> list[str]:
    """Returns a list of rule violations. Empty list = passes the hard scope rules."""
    errs = [f"{v.name} / {s.name}: motor {s.motor} is not a certified commercial motor in motors.json"
            for s in v.stages if s.motor is not None and (s.motor not in MOTORS or not MOTORS[s.motor]["record"].get("cert_org"))]
    if errs:
        return errs   # cannot classify or fly an uncertified motor
    hpr = classify(v)["cert_level"].startswith("Level")
    for i, s in enumerate(v.stages):
        tag = f"{v.name} / {s.name}"
        for m in s.modules:
            if m.kind in FORBIDDEN_MODULES:
                errs.append(f"{tag}: module '{m.kind}' is active control or DIY pyro (out of scope)")
        if s.landing is None or s.landing.primary not in ("rotor", "parachute"):
            errs.append(f"{tag}: every stage needs its own passive landing system")
        if s.motor is not None:
            if s.motor not in MOTORS or not MOTORS[s.motor]["record"].get("cert_org"):
                errs.append(f"{tag}: motor {s.motor} is not a certified commercial motor in motors.json")
        elif v.water is None:
            errs.append(f"{tag}: no motor and not a water rocket")
        if i > 0:
            if s.ignition != "commercial_altimeter":
                errs.append(f"{tag}: upper stage must be lit by a commercial altimeter (not timer-only, motor ejection or DIY)")
            if not set(s.inhibits) & STAGING_INHIBITS or "altitude" not in s.inhibits:
                errs.append(f"{tag}: airstart needs an altitude inhibit plus tilt or time window")
        elif s.ignition != "ground":
            errs.append(f"{tag}: first stage is lit on the ground by the range's launch controller")
        if hpr:
            if s.landing.deploy != "commercial_altimeter" or not s.landing.redundant_altimeters:
                errs.append(f"{tag}: HPR stages deploy with redundant commercial altimeters")
            if s.landing.primary == "rotor" and s.landing.backup != "parachute":
                errs.append(f"{tag}: rotor stages keep a backup parachute")
        if s.landing is not None and s.landing.deploy == "motor_ejection" and s.motor is not None:
            sold = MOTORS[s.motor].get("delays_s", [])
            if s.delay_s not in sold:
                errs.append(f"{tag}: motor ejection needs a delay the {s.motor} is sold with ({', '.join(str(x) for x in sold) or 'none listed'} s)")
    if v.water is not None:
        w = v.water
        if w["psi"] > WATER_MAX_PSI: errs.append(f"{v.name}: {w['psi']} psi > {WATER_MAX_PSI} psi limit")
        if w.get("bottle") != "PET": errs.append(f"{v.name}: rated PET bottles only")
        if not w.get("remote_release"): errs.append(f"{v.name}: remote release required")
    return errs

# ------------------------------------------------------------------ flight and landing
def fly(v: Vehicle, dt: float = 0.005) -> dict:
    """Vertical multi-stage flight (upper bound). Same integrator as high_altitude.fly, plus
    the burnout state of every stage so each separated stage's landing can be sized."""
    if v.water is not None:
        w = pc.water_rocket(P_gauge_psi=v.water["psi"], V_water=v.water["water_l"] / 1000, dry=v.stages[0].dry,
                            d_body=v.stages[0].d, cd=v.stages[0].cd)
        return {"apogee_m": round(w["apogee_m"], 1), "vmax_ms": round(w["vmax_ms"], 1), "mach_max": round(w["vmax_ms"] / 340, 2), "t_apogee_s": round(w["t_apogee_s"], 1),
                "stages": [{"name": v.stages[0].name, "sep_alt_m": round(w["apogee_m"], 1)}]}
    st = [dict(motor=motor(s.motor), dry=s.dry, d=s.d, cd=s.cd) for s in v.stages]
    t = h = vel = 0.0; k, t_ign = 0, 0.0; vmax = Mmax = qmax = 0.0
    s0 = v.stages[0]
    ej_t = (st[0]["motor"].burn_time + s0.delay_s) if (len(st) == 1 and s0.landing and s0.landing.deploy == "motor_ejection" and s0.delay_s is not None) else None
    ej = apo = None
    seps = []
    while True:
        live = st[k:]; m0 = live[0]["motor"]
        tm = t - t_ign
        m = sum(s["dry"] for s in live) + m0.mass(tm) + sum(s["motor"].total_mass for s in live[1:])
        F = m0.thrust(tm)
        rho, a = ha.atmos(v.site_alt + h)
        M = abs(vel) / a
        d = max(s["d"] for s in live)
        q = 0.5 * rho * vel * vel
        D = q * live[0]["cd"] * ha.cd_mult(M) * math.pi * d * d / 4 * (1 if vel >= 0 else -1)
        g = ha.G0 * (ha.RE / (ha.RE + v.site_alt + h)) ** 2
        acc = (F - D) / m - g
        if h <= 0 and acc < 0:
            acc = 0.0
        vel += acc * dt; h += vel * dt; t += dt
        vmax, Mmax, qmax = max(vmax, vel), max(Mmax, M), max(qmax, q)
        if len(live) > 1 and tm > m0.burn_time + v.staging_delay_s:
            seps.append({"name": v.stages[k].name, "sep_alt_m": round(h), "sep_v_ms": round(vel), "sep_mach": round(M, 2)})
            k += 1; t_ign = t
        if ej_t is not None and ej is None and tm >= ej_t:
            ej = {"t_s": round(t, 1), "alt_m": round(h), "v_ms": round(vel, 1)}
        if apo is None and len(st[k:]) == 1 and tm > m0.burn_time and vel < 0:
            apo = (h, t)
        if apo is not None and (ej_t is None or ej is not None):
            break
    h, t = apo
    seps.append({"name": v.stages[-1].name, "sep_alt_m": round(h), "sep_v_ms": 0, "sep_mach": 0})
    out = {"apogee_m": round(h), "vmax_ms": round(vmax), "mach_max": round(Mmax, 2), "t_apogee_s": round(t, 1), "qmax_kPa": round(qmax / 1000), "stages": seps}
    if ej is not None:
        out["ejection"] = ej   # v_ms > 0: still climbing (early); < 0: already falling (late)
    return out

def ejection_options(v: Vehicle) -> list[dict]:
    """Fly a motor-ejection rocket with every delay its motor is sold with; the best is the smallest |v| at ejection."""
    s = v.stages[0]
    res = []
    for dly in MOTORS[s.motor].get("delays_s", []):
        vv = replace(v, stages=[replace(s, delay_s=dly)])
        res.append({"delay_s": dly, **fly(vv)["ejection"]})
    return res

def landing_mass(s: Stage) -> float:
    return s.dry + ((motor(s.motor).total_mass - motor(s.motor).prop_mass) if s.motor else 0.0)

def size_landing(s: Stage, site_alt: float) -> dict:
    """Size (or check) the rotor and backup chute so each stage lands at <= LANDING_TARGET_MS."""
    m = landing_mass(s); rho = pc.rho(site_alt)
    def D_for(c):
        return math.sqrt(4 * 2 * m * pc.G / (rho * c * LANDING_TARGET_MS ** 2) / math.pi)
    L = s.landing
    c_pri = ROTOR_C_EFF if L.primary == "rotor" else CHUTE_CD
    Dp = L.primary_d or D_for(c_pri)
    vp = math.sqrt(2 * m * pc.G / (rho * c_pri * math.pi * Dp ** 2 / 4))
    out = {"stage": s.name, "landing_mass_kg": round(m, 3), "primary": L.primary, "primary_D_m": round(Dp, 2),
           "v_land_ms": round(vp, 2), "landing_J": round(0.5 * m * vp * vp, 1), "drogue": L.drogue}
    if L.backup:
        Db = L.backup_d or D_for(CHUTE_CD)
        out.update(backup="parachute", backup_D_m=round(Db, 2),
                   v_backup_ms=round(math.sqrt(2 * m * pc.G / (rho * CHUTE_CD * math.pi * Db ** 2 / 4)), 2))
    return out

def to_json(v: Vehicle) -> dict:
    return {"name": v.name, "tier": v.tier, "site_alt": v.site_alt, "staging_delay_s": v.staging_delay_s,
            "water": v.water, "stages": [asdict(s) for s in v.stages]}

def from_json(d: dict) -> Vehicle:
    st = [Stage(**{**s, "modules": [Module(**m) for m in s["modules"]], "landing": Landing(**s["landing"]),
                   "inhibits": tuple(s["inhibits"])}) for s in d["stages"]]
    return Vehicle(d["name"], d["tier"], st, d["site_alt"], d["staging_delay_s"], d["water"])

# ------------------------------------------------------------------ tilted launch and wind (single stage)
def fly_tilted(v: Vehicle, angle_deg: float = 0.0, wind_ms: float = 0.0, rail_m: float = 0.91, dt: float = 0.005) -> dict:
    """2-D flight of a single-stage motor rocket off a launch rod tilted angle_deg from vertical
    (toward +x), in a steady wind blowing toward +x. Off the rod the rocket is assumed perfectly
    stable: it always points into the air-relative velocity, so it weathercocks into the wind at
    once. That overstates weathercocking a little, which makes it a pessimistic bound on coast time.
    The straight-up fly() is the other bound (no tilt, no wind, longest coast)."""
    s = v.stages[0]
    mo = motor(s.motor)
    th = math.radians(angle_deg); ux, uy = math.sin(th), math.cos(th)
    A = math.pi * s.d * s.d / 4
    ej_t = (mo.burn_time + s.delay_s) if (s.landing and s.landing.deploy == "motor_ejection" and s.delay_s is not None) else None
    t = x = h = vx = vy = 0.0; on_rail = True; apo = ej = None; off_rail_ms = None
    while True:
        m = s.dry + mo.mass(t); F = mo.thrust(t)
        rho, a = ha.atmos(v.site_alt + h)
        rx, ry = vx - wind_ms, vy
        sp = math.hypot(rx, ry)
        dx, dy = (ux, uy) if (on_rail or sp == 0) else (rx / sp, ry / sp)
        Dm = 0.5 * rho * sp * sp * s.cd * ha.cd_mult(sp / a) * A
        fx, fy = F * dx, F * dy
        if sp > 0:
            fx -= Dm * rx / sp; fy -= Dm * ry / sp
        g = ha.G0 * (ha.RE / (ha.RE + v.site_alt + h)) ** 2
        ax, ay = fx / m, fy / m - g
        if on_rail:
            al = max(ax * ux + ay * uy, 0.0) if (x * ux + h * uy) <= 0 else ax * ux + ay * uy
            ax, ay = al * ux, al * uy
        vx += ax * dt; vy += ay * dt; x += vx * dt; h += vy * dt; t += dt
        if on_rail and x * ux + h * uy >= rail_m:
            on_rail = False; off_rail_ms = round(math.hypot(vx, vy), 1)
        if ej_t is not None and ej is None and t >= ej_t:
            ej = {"t_s": round(t, 1), "alt_m": round(h), "v_ms": round(vy, 1), "speed_ms": round(math.hypot(vx, vy), 1)}
        if apo is None and t > mo.burn_time and vy < 0:
            apo = {"apogee_m": round(h), "t_apogee_s": round(t, 1), "x_at_apogee_m": round(x)}
        if apo is not None and (ej_t is None or ej is not None):
            break
    out = {**apo, "angle_deg": angle_deg, "wind_ms": wind_ms, "off_rod_ms": off_rail_ms}
    if ej is not None:
        out["ejection"] = ej
    return out

LAUNCH_CASES = ((0, 0), (5, 0), (10, 0), (0, 3), (0, 5), (5, 5))   # (rod angle deg, wind m/s)

def ejection_table(v: Vehicle, cases=LAUNCH_CASES) -> list[dict]:
    """Every sold delay x every launch case: when the chute comes out and how fast the rocket is moving."""
    s = v.stages[0]
    rows = []
    for dly in MOTORS[s.motor].get("delays_s", []):
        vv = replace(v, stages=[replace(s, delay_s=dly)])
        for ang, w in cases:
            f = fly_tilted(vv, ang, w)
            e = f["ejection"]
            rows.append({"delay_s": dly, "angle_deg": ang, "wind_ms": w, "t_apogee_s": f["t_apogee_s"], "apogee_m": f["apogee_m"],
                         "eject_vs_top_s": round(e["t_s"] - f["t_apogee_s"], 1), "speed_ms": e["speed_ms"], "v_ms": e["v_ms"]})
    return rows
