# Maplewing commands. Run `make help`. Ubuntu / WSL2, repo in ~/projects/maplewing.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
.PHONY: help setup test sim site renders charts shots serve check desktop all

help:        ## list commands
	@grep -E '^[a-z-]+:.*## ' Makefile | sed 's/:.*## /\t/'

setup:       ## once: .venv with the simulator, tests and chart tools
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements.txt

test:        ## simulator tests: Python and browser agree, scope rules catch bad designs
	$(PY) -m pytest -q sim

sim:         ## rerun the lineup and write sim/lineup.json
	cd sim && ../$(PY) lineup.py

site:        ## rebuild docs/data, docs/models and docs/app from the sim, CAD and parts list
	$(PY) tools/build_site.py

renders:     ## render every CAD part and assembly to PNG (needs: npm i playwright)
	node tools/render.mjs

charts:      ## README charts from the sim data
	$(PY) tools/charts.py

shots:       ## README screenshots and the hero animation (needs playwright and ffmpeg)
	node tools/shots.mjs

check:       ## export-control guard: no Maplewing-3 or Canopy hardware data in public files
	$(PY) tools/check_public.py

serve:       ## website at http://localhost:8000
	$(PY) -m http.server -d docs 8000

desktop:     ## build the desktop app for this computer (needs Rust and the Tauri prerequisites)
	cd desktop && npm ci && npx tauri build

all: sim site test check  ## everything that CI checks
