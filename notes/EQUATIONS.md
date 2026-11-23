# Maplewing: the equations behind the simulator

Every equation here is the one the code actually runs. Each section names the function it comes from. The Python sim and the browser configurator use the same equations, and `sim/test_framework_agree.py` checks that they give the same answers. SI units throughout. Values marked ASSUMED are estimates waiting for test data.

## 1. Atmosphere: 1976 US Standard Atmosphere (`high_altitude.atmos`)

Geometric altitude $z$ is converted to geopotential altitude, using Earth radius $R_E = 6.371\times10^6$ m:

$$h = \frac{R_E\,z}{R_E + z}$$

Within each layer (base $h_0$, base temperature $T_0$, lapse rate $L$):

$$T = T_0 + L\,(h - h_0)$$

$$p = p_0\left(\frac{T}{T_0}\right)^{-g_0/(R L)} \quad (L \neq 0), \qquad p = p_0\,\exp\!\left(-\frac{g_0 (h-h_0)}{R T_0}\right) \quad (L = 0)$$

$$\rho = \frac{p}{R T}, \qquad a = \sqrt{\gamma R T}$$

Here $g_0 = 9.80665$ m/s², $R = 287.053$ J/(kg·K) and $\gamma = 1.4$. The layer bases are at 0, 11, 20, 32, 47, 51, 71 and 84.852 km. Density is taken as zero above 86 km.

Gravity falls off with altitude:

$$g(z) = g_0\left(\frac{R_E}{R_E + z}\right)^2$$

## 2. Flight: vertical, multi-stage (`maplewing_framework.fly`)

Explicit Euler with $\Delta t = 5$ ms:

$$m\,\dot v = F(t) - D - m\,g(z), \qquad \dot z = v$$

$$D = \tfrac12\,\rho\,v^2\,C_D\,C_M(M)\,\frac{\pi d^2}{4}\,\operatorname{sign}(v), \qquad M = \frac{|v|}{a}$$

- $F(t)$ is the certified thrust curve from ThrustCurve.org, linearly interpolated.
- Motor mass falls in proportion to the impulse delivered so far:

$$m_\text{motor}(t) = m_\text{total} - m_\text{prop}\,\frac{I(t)}{I_\text{total}}$$

- $C_D$ is the subsonic drag coefficient (ASSUMED per stage). A ring tail multiplies it by 1.35, which is the Phase 0 ratio (ASSUMED).
- $C_M(M)$ scales drag with Mach number. It is interpolated from (M, factor) = (0, 1.0), (0.8, 1.0), (1.05, 1.65), (1.3, 1.55), (2, 1.15), (3, 0.95), (5, 0.8), (8, 0.75).
- When a stage burns out and its staging delay has passed, the stack drops that stage and lights the next. The diameter used for drag is the largest diameter still flying.
- Apogee is the first step after the last burnout at which $v < 0$.
- For motor-ejection rockets, the ejection time is $t_\text{burn} + t_\text{delay}$. The delay must be one the motor is actually sold with.

## 3. Flight off a tilted rod in wind (`fly_tilted`)

This is a 2-D version for single-stage rockets. The wind $w$ blows toward $+x$, so the velocity relative to the air is:

$$\vec v_\text{rel} = (v_x - w,\; v_y)$$

- On the rod, thrust acts along the rod direction $\hat u = (\sin\theta, \cos\theta)$. Motion is limited to the rod until the rocket has travelled $L_\text{rod}$ (0.91 m by default).
- Off the rod, the rocket is assumed perfectly stable, so thrust points along $\hat v_\text{rel}$. This slightly overstates weathercocking.

$$m\,\dot{\vec v} = F\,\hat e - \tfrac12\rho\,|\vec v_\text{rel}|^2 C_D C_M\,A\;\hat v_\text{rel} - m g\,\hat y$$

With $\theta = 0$ and $w = 0$ this gives exactly the same result as the vertical sim (tested). The speed off the rod is reported, and about 15 m/s is a common minimum.

## 4. Water rocket (`phase0_compare.water_rocket`)

Water phase: the air expands adiabatically. With $P_0$ the gauge pressure plus atmospheric pressure, $V_{a0}$ the starting air volume and $A_n$ the nozzle area:

$$P = P_0\left(\frac{V_{a0}}{V_a}\right)^{\gamma}, \qquad v_e = \sqrt{\frac{2(P - P_a)}{\rho_w}}, \qquad \dot m = \rho_w A_n v_e, \qquad F = \dot m\,v_e$$

Air phase: isentropic blowdown. The flow is choked while $P/P_a > 1.893$:

$$\dot m = A_n P \sqrt{\frac{\gamma}{R T}}\left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}}, \qquad F = \dot m\,v_e + (P_e - P_a)A_n$$

Unchoked:

$$v_e = \sqrt{\frac{2(P - P_a)}{\rho_a}}, \qquad F = \dot m\,v_e$$

The defaults are a 2 L PET bottle and a 21.7 mm nozzle. Euler steps of $10^{-4}$ s. The pressure limit is a rule in the code: no more than 60 psi in flight, proof-tested at 1.5× (90 psi) with the bottle full of water.

## 5. Landing size (`size_landing`)

Steady descent under a rotor or parachute treated as an equivalent drag disc of diameter $D$:

$$v = \sqrt{\frac{2 m g}{\rho\,C\,\pi D^2/4}} \qquad\Longleftrightarrow\qquad D = \sqrt{\frac{8 m g}{\pi\rho\,C\,v^2}}$$

- $C = 1.5$ for a round parachute (typical).
- $C = 1.08$ for a Maplewing rotor at 6° pitch, from the blade-element model in section 6.
- Each stage is sized to land at 6.5 m/s or slower, a rule of thumb to confirm with the RSO.
- Landing energy is $E = \tfrac12 m v^2$.

## 6. Rotor: blade-element autorotation (`rotor_bem.loads`, `descent`)

The rotor has $N$ blades, chord $c$ and fixed pitch $\theta$. For each element at radius $r$ spinning at rate $\Omega$:

$$u_t = \Omega r, \qquad u_p = V - v_i, \qquad \phi = \operatorname{atan2}(u_p, u_t), \qquad \alpha = \theta + \phi$$

$$C_l = a\,\alpha \;\; (\text{capped at } C_{l,\max}), \qquad C_d = C_{d0} + k\,\alpha^2$$

$$dT = N\,q\,c\,dr\,(C_l\cos\phi + C_d\sin\phi), \qquad dQ = N\,q\,c\,dr\,(C_l\sin\phi - C_d\cos\phi)\,r, \qquad q = \tfrac12\rho(u_t^2+u_p^2)$$

Induced velocity: in the windmill-brake state ($V/v_h \geq 2$), momentum theory gives

$$v_i = v_h\left(\frac{x}{2} - \sqrt{\frac{x^2}{4} - 1}\right), \quad x = \frac{V}{v_h}$$

Below that, an empirical fit for the vortex-ring and turbulent-wake states is used. Here $v_h = \sqrt{W/(2\rho\pi R^2)}$.

Steady descent is solved in two steps. First, for each descent speed $V$, find the autorotation rate $\Omega$ at which torque $Q(\Omega) = 0$. Then find the descent speed $V$ at which thrust $T = W$. The assumed blade values are $a = 5$ /rad, $C_{l,\max} = 0.9$ and $C_{d0} = 0.025$ for a thin flat plate at low Reynolds number. Sweeping the pitch gave 6° as the best fixed pitch, with an equivalent disc coefficient of 1.08. The drop tests in the Dewdrop and Seedling plans are what will check this.

## 7. Stability: Barrowman (`phase0_compare.Rocket.stability`)

Normal-force slopes and centre of pressure:

- Ogive nose: $C_{N\alpha} = 2$, $x_\text{cp} = 0.466\,L_\text{nose}$.
- Fins, with $N$ fins, span $s$, root chord $c_r$, tip chord $c_t$, sweep $x_s$ and mid-chord line $l_f$:

$$C_{N\alpha} = \frac{4N(s/d)^2}{1 + \sqrt{1 + \left(\frac{2 l_f}{c_r + c_t}\right)^2}}\left(1 + \frac{r}{s + r}\right)$$

$$x_\text{cp} = x_f + \frac{x_s(c_r + 2c_t)}{3(c_r + c_t)} + \frac16\left(c_r + c_t - \frac{c_r c_t}{c_r + c_t}\right)$$

- Ring tail (a community method, not validated): the ring is treated as $N_\text{eq} = \pi D_m / h$ panels of span $h = (D_m - d)/2$. The struts are ignored, which is conservative for the centre of pressure. The ring's lift is also checked at 70% to see how sensitive the result is.

The stability margin, in calibers, is

$$\frac{x_\text{cp} - x_\text{cg}}{d}$$

## 8. Classification (`classify`) and scope rules (`validate`)

| Rule | Threshold | Source |
|---|---|---|
| FAA Class 1 model rocket | propellant ≤ 125 g, liftoff mass ≤ 1,500 g, no substantial metal | 14 CFR 101.22(a) |
| FAA Class 2 high-power | total impulse ≤ 40,960 N·s | 14 CFR 101.22(b) |
| FAA Class 3 advanced high-power | ≤ 889,600 N·s and below 150 km | 14 CFR 101.22(c), 1.1 |
| NAR/TRA level | largest motor H–I → L1, J–L → L2, M–O → L3 | NAR, Tripoli |
| Motor letter | total impulse doubles per letter (A = 1.26–2.5 N·s) | NFPA 1122/1127 |

`validate()` rejects any design that:

- uses an uncertified motor;
- has any active control, guidance or DIY pyro module;
- has a stage without its own landing system;
- lights an upper stage with anything other than a commercial altimeter with an altitude inhibit plus a tilt or time window;
- has a high-power stage without redundant commercial altimeters;
- has a rotor stage without a backup parachute;
- names a motor-ejection delay the motor isn't sold with;
- is a water rocket above 60 psi, not in PET, or without a remote release.
