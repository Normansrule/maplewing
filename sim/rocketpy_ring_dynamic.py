"""Does the ring tail actually stabilize the 6-DOF RocketPy flight? (MIT licence)
RocketPy's static_margin() ignores generic surfaces, so we test dynamically: launch at
85 deg into a 5 m/s crosswind and compare the peak angle of attack with and without the ring."""
import numpy as np
from rocketpy import Flight, LinearGenericSurface
import phase0_compare as pc
import rocketpy_ring as rr

rr.env.set_atmospheric_model(type="custom_atmosphere", wind_u=[(0, 5.0), (3000, 5.0)], wind_v=[(0, 0), (3000, 0)])

def build(r, ring_on=True, sign=1.0):
    d, L = r.d, r.L_total
    from rocketpy import Rocket
    Iyy = r.dry_mass * L ** 2 / 12
    rk = Rocket(radius=d/2, mass=r.dry_mass, inertia=(Iyy, Iyy, r.dry_mass*d**2/8), power_off_drag=r.cd,
                power_on_drag=r.cd, center_of_mass_without_motor=L - r.cg_dry, coordinate_system_orientation="tail_to_nose")
    mcase = 0.018 if r.motor.total_impulse < 30 else 0.029 if r.motor.total_impulse < 300 else 0.038
    rk.add_motor(rr.motor_for(r.motor, mcase), position=L - r.motor_cg - 0.035)
    rk.add_nose(length=r.L_nose, kind="ogive", position=L)
    if ring_on:
        cna, xcp = r.tail_cna_xcp()
        rk.add_surfaces(LinearGenericSurface(np.pi*d**2/4, d, {"cL_alpha": rr.const(sign*cna), "cQ_beta": rr.const(-sign*cna)}), L - xcp)
    rk.set_rail_buttons(upper_button_position=L*0.5, lower_button_position=0.02)
    return rk

import sys
if __name__ == "__main__":
    name, case = sys.argv[1], sys.argv[2]
    r = [d for d in pc.designs() if d.name == name][0]
    kw = {"ring": dict(), "flipped": dict(sign=-1.0), "none": dict(ring_on=False)}[case]
    f = Flight(rocket=build(r, **kw), environment=rr.env, rail_length=r.rail_len, inclination=85, heading=90,
               terminate_on_apogee=True, max_time=30)
    t = f.angle_of_attack[:, 0]; a = f.angle_of_attack[:, 1]
    burn = r.motor.burn_time + 1.0
    print(f"{name} | {case} | peak AoA after rail {np.max(a[(t < burn) & (t > 0.3)]):.1f} deg | apogee {f.apogee - rr.env.elevation:.0f} m", flush=True)
