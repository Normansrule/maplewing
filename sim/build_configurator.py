#!/usr/bin/env python3
"""Builds web/dist/configurator.html (the published page) from web/configurator.html by inlining
motors-data.js, maplewing-core.js, maplewing-framework.js, the lineup data and lineup-ui.js at the
<!--BUILD:lineup--> marker (MIT licence). Maplewing-3 is left out of the page data until its
export-control review. Run after changing the lineup or motors."""
import json, pathlib
import lineup as lu
from maplewing_framework import to_json
import export_motors_js  # regenerates web/motors-data.js
WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
data = {t: [to_json(v) for v in lu.lineup(t) ] for t in ("fins", "ring")}
parts = [(WEB / f).read_text() for f in ("motors-data.js", "maplewing-core.js", "maplewing-framework.js")]
parts.insert(3, "var LINEUP=" + json.dumps(data, separators=(",", ":")) + ";")
parts.append((WEB / "lineup-ui.js").read_text())
html = (WEB / "configurator.html").read_text().replace("<!--BUILD:lineup-->", "\n".join(f"<script>\n{p}\n</script>" for p in parts))
assert "Maplewing-3" not in json.dumps(data)
(WEB / "dist").mkdir(exist_ok=True)
(WEB / "dist" / "configurator.html").write_text(html)
print("built web/dist/configurator.html", len(html), "bytes")
