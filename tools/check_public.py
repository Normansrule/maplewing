#!/usr/bin/env python3
"""Export-control guard for the public repository (MIT licence).

Maplewing-3 (three stages, near-space capability) and Canopy (full-scale launcher) are held for
export-control review and must not be published. This fails CI if their design data reaches the
repository's published outputs. Mentions in prose that they are held back are allowed.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUBLISHED = [ROOT / "docs", ROOT / "sim", ROOT / "cad", ROOT / "web", ROOT / "exports"]
# Data that would only exist if a held design were included.
FORBIDDEN = [
    (re.compile(r'Vehicle\(\s*"Maplewing-3"'), "Maplewing-3 vehicle definition"),
    (re.compile(r'"name"\s*:\s*"Maplewing-3"'), "Maplewing-3 data in JSON"),
    (re.compile(r"Booster-150|Dart-75"), "Maplewing-3 stage"),
    (re.compile(r"Emergent-3"), "Class 3 high-altitude study"),
    (re.compile(r"(?i)canopy[_-](sizing|engine|propellant|guidance|structure)"), "Canopy hardware study"),
]
SKIP = {".png", ".jpg", ".webp", ".stl", ".woff2", ".ico", ".icns", ".glb"}

bad = []
for base in PUBLISHED:
    for p in base.rglob("*"):
        if p.is_file() and p.suffix not in SKIP and "vendor" not in p.parts and "__pycache__" not in p.parts:
            text = p.read_text(errors="ignore")
            for rx, what in FORBIDDEN:
                if rx.search(text):
                    bad.append(f"{p.relative_to(ROOT)}: {what}")
if bad:
    print("Held for export-control review, must not be public:\n  " + "\n  ".join(bad))
    sys.exit(1)
print("export-control guard: OK (no Maplewing-3 or Canopy hardware data)")
