"""Python and browser must agree (project rule). Runs the browser core under Node and compares
it with phase0_compare.py over a grid of ring-tail Seedling designs. Run: python -m pytest -q"""
import json, subprocess, pathlib, itertools, math
import phase0_compare as pc

CORE = pathlib.Path(__file__).resolve().parent.parent / "web" / "maplewing-core.js"
GRID = [dict(ringD=D/1000, chord=c/1000, len=L/1000, rotor=0.30)
        for D, c, L in itertools.product((45, 55, 70), (30, 40, 60), (450, 550, 700))]

def py_model(p):
    d = 0.0248
    dry = 0.068 + 0.04*(p["len"]-0.55) + 0.2*(p["ringD"]-0.055) + 0.1*(p["chord"]-0.04)
    cd = 0.70 + 0.5*(p["ringD"]-0.055) + 3*(p["chord"]-0.04)
    r = pc.Rocket("grid", d, 0.10, p["len"], dry, 0.32*(p["len"]/0.55), pc.C6_5, p["len"]-0.05, cd=cd,
                  tail={"type": "ring", "D_ring": p["ringD"], "c": p["chord"], "xf": p["len"]-p["chord"]-0.005})
    return r.stability()["margin_cal"], r.fly()["apogee_m"]

def js_models():
    js = f"const m=require({json.dumps(str(CORE))});console.log(JSON.stringify({json.dumps(GRID)}.map(p=>{{const r=m.model(p);return [r.margin,r.apogee]}})))"
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)

def test_python_and_browser_agree():
    worst_m = worst_a = 0.0
    for p, (jm, ja) in zip(GRID, js_models()):
        pm, pa = py_model(p)
        worst_m = max(worst_m, abs(pm - jm)); worst_a = max(worst_a, abs(pa - ja) / pa)
    print(f"worst margin diff {worst_m:.3f} cal, worst apogee diff {100*worst_a:.2f} %")
    assert worst_m < 0.02 and worst_a < 0.02
