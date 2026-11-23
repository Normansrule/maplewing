"""Shared framework checks (MIT licence). Run: python3 -m pytest -q  (or python3 test_framework_agree.py)

1. Python and browser agree on scope-rule errors, FAA class, cert level, apogee and landing sizing
   for every rocket in the lineup (project rule: Python and browser versions must agree).
2. The scope-rule checks catch rule-breaking designs (servo, timer staging, no landing system,
   uncertified motor, over-pressure water rocket).
"""
import json, subprocess, pathlib, copy
import lineup as lu
from maplewing_framework import to_json, from_json, validate

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"

def js_eval(vehicles):
    js = (f"const F=require({json.dumps(str(WEB / 'maplewing-framework.js'))});const vs={json.dumps(vehicles)};"
          "console.log(JSON.stringify(vs.map(v=>({errors:F.validate(v),cls:F.classify(v),"
          "flight:F.fly(v),landing:v.stages.map(s=>F.sizeLanding(s,v.site_alt))}))))")
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)

def test_python_and_browser_agree():
    worst = 0.0
    for tail in ("ring", "fins"):
        rows = lu.run(tail)
        for py, js in zip(rows, js_eval([r["vehicle"] for r in rows])):
            name = py["vehicle"]["name"]
            assert py["errors"] == js["errors"], name
            assert py["class"]["faa_class"] == js["cls"]["faa_class"], name
            assert py["class"]["cert_level"] == js["cls"]["cert_level"], name
            if True:
                d = abs(py["flight"]["apogee_m"] - js["flight"]["apogee_m"]) / py["flight"]["apogee_m"]
                worst = max(worst, d)
                assert d < 0.005, (name, py["flight"]["apogee_m"], js["flight"]["apogee_m"])
                if "ejection" in py["flight"]:
                    pe, je = py["flight"]["ejection"], js["flight"]["ejection"]
                    assert abs(pe["t_s"] - je["t_s"]) <= 0.1 and abs(pe["v_ms"] - je["v_ms"]) <= 0.5, (name, pe, je)
                assert abs(py["flight"]["t_apogee_s"] - js["flight"]["t_apogee_s"]) <= 0.1, (name, "t_apogee", py["flight"]["t_apogee_s"], js["flight"]["t_apogee_s"])
            for a, b in zip(py["landing"], js["landing"]):
                assert abs(a["primary_D_m"] - b["primary_D_m"]) <= 0.011 and abs(a["v_land_ms"] - b["v_land_ms"]) <= 0.011, name
                assert abs(a.get("backup_D_m", 0) - b.get("backup_D_m", 0)) <= 0.011, name
    print(f"framework agree: worst apogee diff {100*worst:.3f} %")

def test_shared_modules_are_identical():
    """A shared_id means one physical design, so every use must have the same mass and kind."""
    seen = {}
    for tail in ("ring", "fins"):
        for v in lu.lineup(tail):
            for s in v.stages:
                for m in s.modules:
                    if m.shared_id:
                        assert seen.setdefault(m.shared_id, (m.kind, m.mass)) == (m.kind, m.mass), m.shared_id

def _bad_variants():
    base = {v.name: to_json(v) for v in lu.lineup("fins")}
    bad = []
    v = copy.deepcopy(base["Maplewing-2"]); v["stages"][1]["modules"].append({"kind": "servo", "mass": 0.05, "shared_id": "", "reusable": True, "metal": False}); bad.append(("servo", v))
    v = copy.deepcopy(base["Maplewing-2"]); v["stages"][1]["ignition"] = "timer"; bad.append(("timer staging", v))
    v = copy.deepcopy(base["Maplewing-2"]); v["stages"][0]["landing"]["primary"] = "none"; bad.append(("no landing", v))
    v = copy.deepcopy(base["Maplewing-1"]); v["stages"][0]["motor"] = "HOMEMADE"; bad.append(("uncertified motor", v))
    v = copy.deepcopy(base["Maplewing-1"]); v["stages"][0]["landing"]["backup"] = None; bad.append(("no backup chute", v))
    v = copy.deepcopy(base["Dewdrop"]); v["water"]["psi"] = 90; bad.append(("water over pressure", v))
    v = copy.deepcopy(base["Taproot"]); v["stages"][0]["delay_s"] = 4; bad.append(("ejection delay not sold", v))
    return bad

def test_rules_catch_bad_designs():
    bad = _bad_variants()
    js = subprocess.run(["node", "-e", f"const F=require({json.dumps(str(WEB / 'maplewing-framework.js'))});"
                         f"console.log(JSON.stringify({json.dumps([v for _, v in bad])}.map(v=>F.validate(v))))"],
                        capture_output=True, text=True, check=True).stdout
    for (label, v), js_errs in zip(bad, json.loads(js)):
        errs = validate(from_json(v))
        assert errs, f"rule check missed: {label}"
        assert js_errs == errs, label
        print(f"  caught {label}: {errs[0]}")

def test_tilted_launch():
    """fly_tilted at 0 deg, no wind, equals fly(); Python and browser give the same ejection table."""
    from maplewing_framework import fly, fly_tilted, ejection_table
    tap = next(v for v in lu.lineup("fins") if v.name == "Taproot")
    f0, t0 = fly(tap), fly_tilted(tap)
    assert (f0["apogee_m"], f0["t_apogee_s"], f0["ejection"]) == (t0["apogee_m"], t0["t_apogee_s"], {k: t0["ejection"][k] for k in f0["ejection"]}), (f0, t0)
    py = ejection_table(tap)
    js = json.loads(subprocess.run(["node", "-e", f"const F=require({json.dumps(str(WEB / 'maplewing-framework.js'))});"
                                    f"console.log(JSON.stringify(F.ejectionTable({json.dumps(to_json(tap))})))"],
                                   capture_output=True, text=True, check=True).stdout)
    assert len(py) == len(js)
    for a, b in zip(py, js):
        assert abs(a["apogee_m"] - b["apogee_m"]) <= 1 and abs(a["speed_ms"] - b["speed_ms"]) <= 0.2 and a["eject_vs_top_s"] == b["eject_vs_top_s"], (a, b)
    print(f"tilted launch: matches straight-up at 0 deg, Python and browser agree on {len(py)} delay x launch cases")

if __name__ == "__main__":
    test_python_and_browser_agree(); test_shared_modules_are_identical(); test_rules_catch_bad_designs(); test_tilted_launch(); print("all framework checks pass")
