#!/usr/bin/env python3
"""README charts (MIT), drawn from the same data the website uses: docs/data/site-data.js.

    docs/assets/readme/charts/<name>-{light,dark}.png

Two hues only (maple red, sky blue), checked for colour-blind separation on both surfaces.
Usage: python tools/charts.py   (needs matplotlib; `make charts`)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "readme" / "charts"
G = 9.80665
RHO = 1.225 * ((288.15 - 0.0065 * 1300) / 288.15) ** 4.2559  # 1,300 m field, as in the sim

THEMES = {
    "light": dict(bg="#fcfcfb", ink="#16181b", ink2="#4a5059", grid="#e4e6e9", red="#c4261c", blue="#2f6ea3"),
    "dark": dict(bg="#101215", ink="#eef0f2", ink2="#a9b0b9", grid="#262a30", red="#ef5244", blue="#4f93d1"),
}


def load() -> dict:
    src = (ROOT / "docs" / "data" / "site-data.js").read_text()
    return json.loads(src[src.index("{"): src.rindex("}") + 1])


def fonts() -> None:
    """Use the site's Archivo (variable woff2) when fontTools and brotli are installed, else DejaVu Sans."""
    family = "DejaVu Sans"
    try:
        import tempfile
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
        tmp = Path(tempfile.mkdtemp())
        for wght, style in ((400, "Regular"), (700, "Bold")):
            f = TTFont(ROOT / "docs" / "vendor" / "fonts" / "archivo-latin-standard-normal.woff2")
            f = instantiateVariableFont(f, {"wght": wght, "wdth": 100}, updateFontNames=False)
            f.flavor = None
            for rec in f["name"].names:
                if rec.nameID in (1, 16):
                    rec.string = "Archivo"
                elif rec.nameID in (2, 17):
                    rec.string = style
            f["OS/2"].usWeightClass = wght
            f.save(tmp / f"Archivo-{style}.ttf")
            font_manager.fontManager.addfont(str(tmp / f"Archivo-{style}.ttf"))
        family = "Archivo"
    except Exception as e:  # fonts are cosmetic; never fail the build over them
        print("charts: using DejaVu Sans,", e)
    plt.rcParams.update({"font.family": [family], "font.size": 11, "mathtext.fontset": "dejavusans"})


def frame(t: dict, w: float, h: float, title: str, sub: str):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(t["bg"]); ax.set_facecolor(t["bg"])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["ink2"], length=0, labelsize=10)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8); ax.set_axisbelow(True)
    fig.text(0.02, 1 - 0.14 / h, title, color=t["ink"], fontsize=15, fontweight="bold", va="top")
    fig.text(0.02, 1 - 0.42 / h, sub, color=t["ink2"], fontsize=10.5, va="top")
    return fig, ax


def save(fig, name: str, mode: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}-{mode}.png"
    fig.savefig(p, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("chart", p.relative_to(ROOT))


def apogee(d: dict, t: dict, mode: str) -> None:
    rows = sorted(d["lineup"], key=lambda r: r["apogee_m"])
    fig, ax = frame(t, 8, 4.2, "Simulated apogee", "Six configurations on one framework. Red lands on a rotor, blue on a parachute or other recovery.")
    y = range(len(rows))
    rotor = [r["stages"][-1]["landing"] == "rotor" for r in rows]
    ax.barh(y, [r["apogee_m"] for r in rows], height=0.56, color=[t["red"] if k else t["blue"] for k in rotor])
    ax.set_xscale("log"); ax.set_xlim(8, max(r["apogee_m"] for r in rows) * 3)
    ax.set_yticks(list(y), [f'{r["name"]}  ·  {r["stages"][0]["motor"] if r["stages"][0]["motor"] != "None" else "water"}' for r in rows], color=t["ink"])
    for i, r in enumerate(rows):
        ax.text(r["apogee_m"] * 1.08, i, f'{r["apogee_m"]:,} m', va="center", color=t["ink2"], fontsize=10)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f} m"))
    ax.set_xlabel("apogee (log scale)", color=t["ink2"], fontsize=10)
    fig.subplots_adjust(left=0.27, right=0.97, top=0.8, bottom=0.14)
    save(fig, "apogee", mode)


def descent(d: dict, t: dict, mode: str) -> None:
    R = d["rotor"]
    seed = next(r for r in d["lineup"] if r["name"] == "Seedling")
    m = seed["stages"][0]["mass_kg"]
    fig, ax = frame(t, 8, 4.2, "Rotor against parachute, same diameter",
                    f"Seedling at {m * 1000:.0f} g, air at 1,300 m. Steady descent $v=\\sqrt{{2mg/\\rho C A}}$.")
    ds = [0.15 + i * 0.005 for i in range(71)]
    for C, col, name, dy in ((R["C_rotor"], t["red"], "Rotor", 0.35), (R["C_chute"], t["blue"], "Parachute", -0.35)):
        v = [math.sqrt(2 * m * G / (RHO * C * math.pi * D * D / 4)) for D in ds]
        ax.plot(ds, v, color=col, linewidth=2.2, solid_capstyle="round")
        ax.text(ds[-1] + 0.008, v[-1] + dy, f"{name}, C = {C}", color=t["ink"], va="center", fontsize=10)
    ax.axhline(R["v_target_ms"], color=t["ink2"], linewidth=1, linestyle=(0, (4, 3)))
    ax.text(0.5, R["v_target_ms"] - 0.45, f'target {R["v_target_ms"]} m/s', color=t["ink2"], fontsize=10, ha="right")
    d0 = seed["stages"][0]["landing_D_m"]
    v0 = math.sqrt(2 * m * G / (RHO * R["C_rotor"] * math.pi * d0 * d0 / 4))
    ax.plot([d0], [v0], "o", ms=8, color=t["red"], mec=t["bg"], mew=2)
    ax.annotate(f"as built: {d0:.2f} m, {v0:.1f} m/s in this model\n(full simulator: {seed['stages'][0]['v_land_ms']} m/s)", (d0, v0), (0.335, 7.6), textcoords="data", color=t["ink"], fontsize=10,
                arrowprops=dict(arrowstyle="-", color=t["ink2"], linewidth=0.8, shrinkB=6))
    ax.set_xlim(0.15, 0.56); ax.set_ylim(0, 9)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_xlabel("diameter (m)", color=t["ink2"], fontsize=10); ax.set_ylabel("descent (m/s)", color=t["ink2"], fontsize=10)
    fig.subplots_adjust(left=0.09, right=0.8, top=0.8, bottom=0.14)
    save(fig, "descent", mode)


def mass(d: dict, t: dict, mode: str) -> None:
    parts = [p for p in d["cad"]["parts"] if p.get("budget_g")]
    parts.sort(key=lambda p: (p["rocket"], p["title"]))
    fig, ax = frame(t, 8, 0.9 + 0.42 * len(parts), "CAD mass against budget",
                    "Dot is the CAD mass of one part. Tick is its budget. Red means the part is over budget.")
    for i, p in enumerate(parts):
        over = p["mass_g"] > p["budget_g"]
        ax.plot([p["budget_g"]] * 2, [i - 0.28, i + 0.28], color=t["ink"], linewidth=2)
        ax.plot([min(p["mass_g"], p["budget_g"]), max(p["mass_g"], p["budget_g"])], [i, i], color=t["grid"], linewidth=3)
        ax.plot([p["mass_g"]], [i], "o", ms=8, color=t["red"] if over else t["blue"], mec=t["bg"], mew=2)
        pct = 100 * (p["mass_g"] / p["budget_g"] - 1)
        ax.text(max(p["mass_g"], p["budget_g"]) * 1.1, i, f'{p["mass_g"]:g} g  ({pct:+.0f}%)', va="center", color=t["ink2"], fontsize=9.5)
    ax.set_xscale("log")
    ax.set_yticks(range(len(parts)), [f'{p["rocket"]} · {p["title"]}' for p in parts], color=t["ink"])
    ax.invert_yaxis()
    ax.set_xlim(min(p["mass_g"] for p in parts) / 1.6, max(max(p["mass_g"], p["budget_g"]) for p in parts) * 4.5)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g} g"))
    fig.subplots_adjust(left=0.36, right=0.97, top=1 - 0.95 / fig.get_figheight(), bottom=0.5 / fig.get_figheight())
    save(fig, "mass", mode)


def cost(d: dict, t: dict, mode: str) -> None:
    rows = [r for r in d["bom"] if r["rocket"] == "Seedling" and r["line_usd"]]
    groups: dict[str, float] = {}
    for r in rows:
        groups[r["group"]] = groups.get(r["group"], 0) + r["line_usd"]
    names = {"printed": "Printed parts (PETG)", "airframe": "Airframe and hardware", "per-flight": "Motors and wadding", "ground": "Ground support"}
    items = sorted(groups.items(), key=lambda kv: kv[1])
    total = sum(groups.values())
    fig, ax = frame(t, 8, 3.4, f"Seedling, first flying day: ${total:,.2f}",
                    "Retailer listing prices with sources in exports/bom. Items still waiting on a quote are not counted.")
    ax.barh(range(len(items)), [v for _, v in items], height=0.56, color=t["red"])
    ax.set_yticks(range(len(items)), [names.get(k, k) for k, _ in items], color=t["ink"])
    for i, (_, v) in enumerate(items):
        ax.text(v + total * 0.012, i, f"${v:,.2f}", va="center", color=t["ink2"], fontsize=10)
    ax.set_xlim(0, max(groups.values()) * 1.22)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    fig.subplots_adjust(left=0.27, right=0.97, top=0.76, bottom=0.12)
    save(fig, "cost", mode)


def main() -> None:
    fonts()
    d = load()
    for mode, t in THEMES.items():
        for f in (apogee, descent, mass, cost):
            f(d, t, mode)


if __name__ == "__main__":
    main()
