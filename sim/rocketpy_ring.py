"""RocketPy 6-DOF cross-check of every Phase 0 design, ring tails included (MIT licence).
Ring tails enter RocketPy as a LinearGenericSurface whose cL_alpha and CP come from the
same equivalent-fin model as phase0_compare.py, so this checks the flight dynamics and
integration, not the ring aerodynamics (that needs CFD or tunnel data)."""
import numpy as np
from rocketpy import Environment, GenericMotor, Rocket, Flight, LinearGenericSurface
import phase0_compare as pc

env = Environment(latitude=32.99, longitude=-106.97, elevation=1300)
env.set_atmospheric_model(type="standard_atmosphere")

def motor_for(m, d_case):
    curve = [list(p) for p in m.curve]   # the ThrustCurve.org .eng points, unresampled
    L = 0.07 if m.total_impulse < 30 else 0.19 if m.total_impulse < 300 else 0.25
    return GenericMotor(thrust_source=curve, burn_time=m.burn_time, chamber_radius=d_case / 2,
                        chamber_height=L, chamber_position=L / 2, propellant_initial_mass=m.prop_mass,
                        nozzle_radius=d_case / 4, dry_mass=m.total_mass - m.prop_mass,
                        dry_inertia=(1e-4, 1e-4, 1e-5), center_of_dry_mass_position=L / 2, nozzle_position=0,
                        coordinate_system_orientation="nozzle_to_combustion_chamber")

def const(c):
    def f(alpha, beta, mach, reynolds, pitch_rate, yaw_rate, roll_rate):
        return c
    return f

def run(r: pc.Rocket):
    d, L = r.d, r.L_total
    mcase = 0.018 if r.motor.total_impulse < 30 else 0.029 if r.motor.total_impulse < 300 else 0.038
    Iyy = r.dry_mass * L ** 2 / 12
    rk = Rocket(radius=d / 2, mass=r.dry_mass, inertia=(Iyy, Iyy, r.dry_mass * d ** 2 / 8),
                power_off_drag=r.cd, power_on_drag=r.cd, center_of_mass_without_motor=L - r.cg_dry,
                coordinate_system_orientation="tail_to_nose")
    rk.add_motor(motor_for(r.motor, mcase), position=L - r.motor_cg - 0.035)
    rk.add_nose(length=r.L_nose, kind="ogive", position=L)
    t = r.tail
    if t["type"] == "fins":
        rk.add_trapezoidal_fins(n=t["N"], root_chord=t["cr"], tip_chord=t["ct"], span=t["s"],
                                sweep_length=t["xs"], position=L - t["xf"])
    else:
        cna, xcp = r.tail_cna_xcp()
        ring = LinearGenericSurface(reference_area=np.pi * d ** 2 / 4, reference_length=d,
                                    coefficients={"cL_alpha": const(cna), "cQ_beta": const(-cna)}, name="ring tail")
        rk.add_surfaces(ring, L - xcp)
    rk.set_rail_buttons(upper_button_position=L * 0.5, lower_button_position=0.02)
    f = Flight(rocket=rk, environment=env, rail_length=r.rail_len, inclination=90, heading=0,
               terminate_on_apogee=True)
    return rk.static_margin(0), f.apogee - env.elevation, f.out_of_rail_velocity

if __name__ == "__main__":
    print("design | sim margin | RocketPy margin | sim apogee | RocketPy apogee | RocketPy rail exit")
    for r in pc.designs():
        s, fl = r.stability(), r.fly()
        m, ap, vr = run(r)
        print(f"{r.name} | {s['margin_cal']:.2f} | {m:.2f} | {fl['apogee_m']:.0f} | {ap:.0f} | {vr:.1f}")
