"""RocketPy 6-DOF cross-check of the Sapling L1 finned design (MIT licence).
Uses the same simplified two-level H128W curve as phase0_compare.py, so it checks
the physics, not the motor data. Swap in the ThrustCurve.org .eng file for real runs."""
import numpy as np
from rocketpy import Environment, GenericMotor, Rocket, Flight
import phase0_compare as pc

m = pc.H128W
t = np.linspace(0, m.burn_time, 200)
curve = [[ti, m.thrust(ti)] for ti in t] + [[m.burn_time + 1e-3, 0.0]]
motor = GenericMotor(thrust_source=curve, burn_time=m.burn_time, chamber_radius=0.0145,
                     chamber_height=0.19, chamber_position=0.095, propellant_initial_mass=m.prop_mass,
                     nozzle_radius=0.006, dry_mass=m.total_mass - m.prop_mass, dry_inertia=(0.001, 0.001, 0.0001),
                     center_of_dry_mass_position=0.095, nozzle_position=0, coordinate_system_orientation="nozzle_to_combustion_chamber")
env = Environment(latitude=32.99, longitude=-106.97, elevation=1300)
env.set_atmospheric_model(type="standard_atmosphere")
d = 0.0574
r = Rocket(radius=d/2, mass=1.30, inertia=(0.17, 0.17, 0.0006), power_off_drag=0.48, power_on_drag=0.48,
           center_of_mass_without_motor=1.25-0.70, coordinate_system_orientation="tail_to_nose")
r.add_motor(motor, position=1.25-1.25)
r.add_nose(length=0.25, kind="ogive", position=1.25)
r.add_trapezoidal_fins(n=3, root_chord=0.14, tip_chord=0.055, span=0.06, sweep_length=0.075, position=1.25-1.10)
r.set_rail_buttons(upper_button_position=0.6, lower_button_position=0.1)
print("RocketPy static margin at liftoff (cal):", round(r.static_margin(0), 2))
f = Flight(rocket=r, environment=env, rail_length=1.83, inclination=90, heading=0, terminate_on_apogee=True)
print("RocketPy apogee AGL (m):", round(f.apogee - env.elevation, 1), " rail exit (m/s):", round(f.out_of_rail_velocity, 1))
