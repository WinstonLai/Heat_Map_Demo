# Event Participation Heat Map - Singapore

A demo of how a heat map helps with event planning. It mocks a year of events across Singapore (1,500 events, 6 event
types, 25 locations) and plots **participation rate** (attendees / invited) as an interactive heat map.

**Live demo:** https://winstonlai.github.io/Heat_Map_Demo/

## Run

```bash
uv sync
uv run generate_map.py            # writes docs/index.html and opens it
uv run generate_map.py --no-open  # just write the file
```

The output is a standalone HTML file; open it in any browser. GitHub Pages serves `docs/` from `main`, so
regenerate and push to update the live map.

## What the map shows

- **Heat layers** - participation rate per ~500 m cell. Blue = ~30% turnout, red = 90%+. Toggle *All events* or any single
  event type (top-right layer control) to see where each type works.
- **Monthly timeline** - off by default; enable it to watch hot spots shift through the year.
- **Hot spots** (red flame markers) - high turnout in areas that already host many events: proven demand.
- **Opportunity zones** (green stars) - high turnout but few events: demand is outrunning supply, so these are the
  best places to add events.
- Side panel with the ranked lists; click any marker for details and the best-performing event type there.

## The planning story

A plain event count would point at the busiest places (Marina Bay, Orchard, Tampines). The participation-rate heat
map also surfaces places like Punggol, Sengkang and Yishun, where few events are held but nearly everyone invited
turns up. Those are the cheapest wins for the next programme.

## Files

- `generate_map.py` - mock data (`make_events`), analysis (`find_hotspots`), map (`build_map`)
- `pyproject.toml` / `uv.lock` - dependencies (folium, pandas, numpy), managed with uv

All data is randomly generated (fixed seed 42) and does not reflect real events.
