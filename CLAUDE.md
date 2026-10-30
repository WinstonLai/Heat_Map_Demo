# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies are managed with **uv** (`pyproject.toml` / `uv.lock`); don't use pip or `python -m venv`.

```bash
uv sync                           # create .venv and install folium, pandas, numpy
uv run generate_map.py            # regenerate docs/index.html and open it in the browser
uv run generate_map.py --no-open  # regenerate only
```

There is no test suite, linter or build step. To verify a change, regenerate the map and view it. The browser
automation tool rejects `file://` URLs, so serve it instead: `python3 -m http.server 8765 --bind 127.0.0.1` from the
repo root, then open `http://127.0.0.1:8765/docs/index.html`.

`requires-python` is `>=3.9` (`uv run` currently resolves to 3.12), so avoid 3.10+-only syntax.

## Architecture

The whole project is one script, `generate_map.py`, which runs a pipeline and writes a standalone folium (Leaflet)
HTML file:

`make_events()` -> `find_hotspots()` -> `build_map()` -> `docs/index.html`

- **Mock data** (`HUBS`, `EVENT_TYPES`, `SEASONALITY` at the top): events are sampled per (hub, event type) pair, with
  supply = hub weight x type affinity. Turnout is `engagement x affinity x seasonality + noise`. The seed is fixed
  (42), so output is deterministic. The data is deliberately shaped so that Punggol, Sengkang and Yishun have very
  high turnout but few events; this is the "under-served demand" story the demo tells, so changing hub engagement or
  weights can break the narrative.
- **Analysis**: `aggregate()` bins events onto a lat/lon grid (`GRID_DEG`, ~1 km). **Hot spots** are the highest-rate
  cells in the busiest quartile by event count. **Opportunity zones** are top-quartile-rate cells with at or below the
  median event count. The two sets are kept disjoint by those thresholds, and each area appears at most once.
- **Map**: heat layers use `aggregate()` at a finer cell size, with weight = mean participation rate scaled between
  `RATE_FLOOR` and `RATE_CEIL`. There is one layer per event type plus "All events" and a monthly `HeatMapWithTime`.
  The side panel is raw HTML/CSS injected via `folium.Element`.

## Gotchas

- The panel HTML is a Jinja template under the hood (folium/branca). A literal `{#` in it, such as the CSS selector
  `#panel` right after an opening `{{`, is parsed as a comment and breaks the build. Keep a space or restructure.
- The basemap is OpenStreetMap on purpose: current folium warns that CartoDB tiles need an API key.

## Publishing

The live demo (https://winstonlai.github.io/Heat_Map_Demo/) is GitHub Pages serving `docs/` from `main`. The output
path is `docs/index.html` for that reason. To update the live map, regenerate, then commit and push `docs/index.html`.
