"""Singapore event participation heat map demo.

Generates mock event data, finds participation hot spots and under-served
"opportunity zones", and writes a standalone interactive map to
event_heatmap.html.

    uv run generate_map.py [--no-open]
"""
import argparse
import webbrowser
from pathlib import Path

import folium
import numpy as np
import pandas as pd
from folium import plugins

OUTPUT = Path(__file__).parent / "event_heatmap.html"
SG_CENTER = (1.3521, 103.8198)
SG_VIEW = [[1.22, 103.62], [1.48, 104.05]]
GRADIENT = {0.2: "#2c7bb6", 0.4: "#abd9e9", 0.6: "#ffffbf", 0.8: "#fdae61", 1.0: "#d7191c"}

N_EVENTS = 1500
GRID_DEG = 0.01  # ~1.1 km analysis cell
MIN_EVENTS_HOTSPOT = 8
RATE_FLOOR, RATE_CEIL = 0.30, 0.90  # participation rates mapped onto the 0-1 heat scale

# name: (lat, lon, relative event supply, base engagement, jitter in degrees)
HUBS = {
    "Orchard": (1.3040, 103.8318, 1.6, 0.55, 0.003),
    "Marina Bay": (1.2830, 103.8540, 1.5, 0.62, 0.003),
    "Bugis": (1.3009, 103.8559, 1.2, 0.58, 0.003),
    "Kallang": (1.3114, 103.8714, 1.0, 0.60, 0.004),
    "Tampines": (1.3540, 103.9440, 1.5, 0.66, 0.004),
    "Pasir Ris": (1.3720, 103.9490, 0.8, 0.64, 0.003),
    "Bedok": (1.3236, 103.9290, 1.0, 0.52, 0.004),
    "Jurong East": (1.3330, 103.7436, 1.3, 0.50, 0.004),
    "Bukit Batok": (1.3490, 103.7496, 0.8, 0.48, 0.004),
    "Clementi": (1.3150, 103.7650, 0.9, 0.57, 0.004),
    "Queenstown": (1.2942, 103.8060, 0.8, 0.54, 0.004),
    "Toa Payoh": (1.3343, 103.8563, 1.0, 0.56, 0.004),
    "Bishan": (1.3526, 103.8352, 1.1, 0.68, 0.004),
    "Serangoon": (1.3500, 103.8736, 0.7, 0.52, 0.004),
    "Hougang": (1.3612, 103.8863, 0.9, 0.50, 0.004),
    "Sengkang": (1.3917, 103.8950, 0.35, 0.78, 0.004),
    "Punggol": (1.4040, 103.9020, 0.30, 0.82, 0.004),
    "Yishun": (1.4304, 103.8354, 0.40, 0.74, 0.004),
    "Woodlands": (1.4370, 103.7860, 0.50, 0.70, 0.004),
    "Ang Mo Kio": (1.3691, 103.8454, 1.0, 0.59, 0.004),
    "Geylang": (1.3200, 103.8870, 0.7, 0.46, 0.003),
    "Bukit Timah": (1.3294, 103.8021, 0.6, 0.63, 0.004),
    "one-north": (1.2995, 103.7870, 0.7, 0.55, 0.003),
    "Sentosa": (1.2494, 103.8303, 0.5, 0.60, 0.003),
    "Choa Chu Kang": (1.3840, 103.7470, 0.4, 0.45, 0.004),
}

# event type -> {hub: affinity multiplier on event supply}; unlisted hubs are 1.0
EVENT_TYPES = {
    "Fitness & Sports": {"Punggol": 3, "Bedok": 2, "Pasir Ris": 2, "Kallang": 2, "Sengkang": 2},
    "Food & Markets": {"Geylang": 3, "Bugis": 2.5, "Tampines": 2, "Orchard": 2, "Toa Payoh": 1.5},
    "Arts & Culture": {"Bugis": 3, "Marina Bay": 2.5, "Queenstown": 1.5, "Orchard": 1.5},
    "Tech Meetups": {"one-north": 4, "Jurong East": 2.5, "Marina Bay": 2, "Clementi": 1.5},
    "Community Volunteering": {"Woodlands": 3, "Yishun": 3, "Hougang": 2, "Bukit Batok": 2, "Choa Chu Kang": 2},
    "Music & Concerts": {"Marina Bay": 4, "Sentosa": 3, "Kallang": 3, "Orchard": 1.5},
}

# month -> participation multiplier per type, for the time slider
SEASONALITY = {
    "Fitness & Sports": {1: 1.12, 2: 1.10, 3: 1.06, 11: 0.95, 12: 0.92},
    "Food & Markets": {11: 1.08, 12: 1.15},
    "Music & Concerts": {9: 1.08, 10: 1.10, 11: 1.12, 12: 1.15},
}


def make_events(seed=42):
    """Mock one year of events: a hub, a type, an invite list and a turnout each."""
    rng = np.random.default_rng(seed)
    pairs = [(hub, etype) for hub in HUBS for etype in EVENT_TYPES]
    weights = np.array([HUBS[h][2] * EVENT_TYPES[t].get(h, 1.0) for h, t in pairs])
    counts = rng.multinomial(N_EVENTS, weights / weights.sum())

    rows = []
    for (hub, etype), n in zip(pairs, counts):
        lat0, lon0, _, engagement, jitter = HUBS[hub]
        affinity = EVENT_TYPES[etype].get(hub, 1.0)
        for _ in range(n):
            month = int(rng.integers(1, 13))
            season = SEASONALITY.get(etype, {}).get(month, 1.0)
            # a better-matched event type draws slightly better turnout
            p = engagement * (1 + 0.1 * (affinity - 1)) * season + rng.normal(0, 0.05)
            invited = int(rng.integers(40, 600))
            attended = int(rng.binomial(invited, float(np.clip(p, 0.10, 0.97))))
            rows.append({
                "event_type": etype,
                "area": hub,
                "lat": lat0 + rng.normal(0, jitter),
                "lon": lon0 + rng.normal(0, jitter * 1.1),
                "date": pd.Timestamp(2026, month, int(rng.integers(1, 29))),
                "invited": invited,
                "attended": attended,
            })

    df = pd.DataFrame(rows)
    df["participation_rate"] = df["attended"] / df["invited"]
    df.insert(0, "event_id", np.arange(1, len(df) + 1))
    return df


def aggregate(df, cell_deg):
    """Collapse events onto a lat/lon grid: mean rate and event count per cell."""
    cells = df.assign(
        gy=np.floor(df["lat"] / cell_deg).astype(int),
        gx=np.floor(df["lon"] / cell_deg).astype(int),
    )
    out = cells.groupby(["gy", "gx"]).agg(
        n_events=("event_id", "size"),
        mean_rate=("participation_rate", "mean"),
        attendees=("attended", "sum"),
        area=("area", lambda s: s.mode().iat[0]),
    ).reset_index()
    out["lat"] = (out["gy"] + 0.5) * cell_deg
    out["lon"] = (out["gx"] + 0.5) * cell_deg
    return out


def best_type(df, cell):
    """Event type with the best mean turnout inside one analysis cell."""
    gy, gx = cell["gy"], cell["gx"]
    inside = df[(np.floor(df["lat"] / GRID_DEG) == gy) & (np.floor(df["lon"] / GRID_DEG) == gx)]
    by_type = inside.groupby("event_type")["participation_rate"].agg(["mean", "size"])
    return by_type["mean"].idxmax() if len(by_type) else "-"


def find_hotspots(df, n_hot=5, n_opp=3):
    """Hot spots = highest turnout among the busiest quarter of cells (by event count).
    Opportunity zones = turnout in the top quartile but few events (demand > supply).
    The two are disjoint by construction; each area appears at most once."""
    grid = aggregate(df, GRID_DEG)
    supply_cut = grid["n_events"].median()
    busy_cut = grid["n_events"].quantile(0.75)
    rate_cut = grid["mean_rate"].quantile(0.75)

    established = grid[(grid["n_events"] > busy_cut) & (grid["n_events"] >= MIN_EVENTS_HOTSPOT)]
    underserved = grid[(grid["n_events"] <= supply_cut) & (grid["n_events"] >= 3) & (grid["mean_rate"] >= rate_cut)]

    hot = established.sort_values("mean_rate", ascending=False).drop_duplicates("area").head(n_hot)
    opp = underserved.sort_values("mean_rate", ascending=False).drop_duplicates("area").head(n_opp)

    for table in (hot, opp):
        table["top_type"] = [best_type(df, row) for _, row in table.iterrows()]
    return hot.reset_index(drop=True), opp.reset_index(drop=True)


def heat_points(df, cell_deg):
    """[lat, lon, weight] per cell, weight = mean participation rate scaled to 0-1."""
    grid = aggregate(df, cell_deg)
    w = ((grid["mean_rate"] - RATE_FLOOR) / (RATE_CEIL - RATE_FLOOR)).clip(0.05, 1.0)
    return [[la, lo, wt] for la, lo, wt in zip(grid["lat"], grid["lon"], w)]


def add_markers(fmap, table, name, color, icon, headline, advice):
    group = folium.FeatureGroup(name=name, show=True)
    for _, r in table.iterrows():
        html = (
            f"<b>{r['area']}</b> &middot; <i>{headline}</i><br>"
            f"Participation rate: <b>{r['mean_rate']:.0%}</b><br>"
            f"Events held: {int(r['n_events'])} &middot; Attendees: {int(r['attendees']):,}<br>"
            f"Best-performing type: {r['top_type']}<br><span style='color:#555'>{advice}</span>"
        )
        folium.Marker(
            [r["lat"], r["lon"]],
            popup=folium.Popup(html, max_width=260),
            tooltip=f"{r['area']} - {r['mean_rate']:.0%}",
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
        ).add_to(group)
    group.add_to(fmap)


def panel_html(df, hot, opp):
    def items(table, tag):
        return "".join(
            f"<li><b>{r['area']}</b> <span class='m'>{r['mean_rate']:.0%} &middot; {int(r['n_events'])} events"
            f"{' &middot; ' + r['top_type'] if tag else ''}</span></li>"
            for _, r in table.iterrows()
        )

    return f"""
    <style>
      #panel {{position:fixed; top:10px; left:56px; z-index:9999; width:270px; max-height:calc(100vh - 20px);
        overflow:auto; background:rgba(255,255,255,.95); border-radius:8px; padding:12px 14px;
        font:13px/1.4 system-ui,sans-serif; color:#222; box-shadow:0 2px 10px rgba(0,0,0,.25)}}
      #panel h3 {{margin:0 0 2px; font-size:15px}} #panel h4 {{margin:10px 0 3px; font-size:13px}}
      #panel ol {{margin:0; padding-left:18px}} #panel .m {{color:#666; font-size:12px; display:block}}
      #panel .bar {{height:10px; border-radius:5px; margin:4px 0 2px;
        background:linear-gradient(90deg,{GRADIENT[0.2]},{GRADIENT[0.4]},{GRADIENT[0.6]},{GRADIENT[0.8]},{GRADIENT[1.0]})}}
      #panel .sc {{display:flex; justify-content:space-between; font-size:11px; color:#666}}
      #panel p {{margin:6px 0 0; font-size:12px; color:#444}}
      @media (max-width:600px) {{ #panel {{width:auto; right:10px; top:auto; bottom:10px; max-height:40vh}}}}
    </style>
    <div id="panel">
      <h3>Event participation - Singapore</h3>
      <span class="m">{len(df):,} mock events &middot; {df['attended'].sum():,} attendees &middot; avg rate {df['participation_rate'].mean():.0%}</span>
      <div class="bar"></div>
      <div class="sc"><span>{RATE_FLOOR:.0%} turnout</span><span>{RATE_CEIL:.0%}+</span></div>
      <h4>&#128293; Hot spots (proven demand)</h4><ol>{items(hot, True)}</ol>
      <h4>&#11088; Opportunity zones</h4><ol>{items(opp, True)}</ol>
      <p>Opportunity zones turn out strongly but host few events: run more events here first.
      Use the layer control (top right) to compare event types or play the monthly timeline.</p>
    </div>"""


def build_map(df, hot, opp):
    fmap = folium.Map(location=SG_CENTER, zoom_start=11, tiles=None, min_zoom=10, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="Street map").add_to(fmap)
    fmap.fit_bounds(SG_VIEW)

    heat_opts = dict(gradient=GRADIENT, radius=28, blur=22, min_opacity=0.35, max_zoom=14)
    plugins.HeatMap(heat_points(df, 0.005), name="All events", show=True, **heat_opts).add_to(fmap)
    for etype in EVENT_TYPES:
        plugins.HeatMap(heat_points(df[df["event_type"] == etype], 0.006),
                        name=etype, show=False, **heat_opts).add_to(fmap)

    months = pd.period_range("2026-01", "2026-12", freq="M")
    frames = [heat_points(df[df["date"].dt.to_period("M") == m], 0.008) for m in months]
    plugins.HeatMapWithTime(frames, index=[m.strftime("%b %Y") for m in months], name="Monthly timeline",
                            auto_play=False, radius=22, gradient=GRADIENT, min_opacity=0.35,
                            use_local_extrema=False, display_index=True, show=False).add_to(fmap)

    add_markers(fmap, hot, "Hot spots", "red", "fire", "hot spot", "Proven demand: keep programming here.")
    add_markers(fmap, opp, "Opportunity zones", "green", "star", "under-served",
                "High turnout, few events: add events here.")

    plugins.Fullscreen().add_to(fmap)
    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(fmap)
    plugins.MeasureControl(position="topright", primary_length_unit="kilometers").add_to(fmap)
    folium.LayerControl(collapsed=False, position="topright").add_to(fmap)
    fmap.get_root().html.add_child(folium.Element(panel_html(df, hot, opp)))
    return fmap


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-open", action="store_true", help="don't open the map in a browser")
    args = parser.parse_args()

    df = make_events()
    hot, opp = find_hotspots(df)
    build_map(df, hot, opp).save(str(OUTPUT))

    print(f"{len(df):,} mock events, overall participation {df['participation_rate'].mean():.1%}")
    print("\nHot spots:\n", hot[["area", "mean_rate", "n_events", "top_type"]].to_string(index=False))
    print("\nOpportunity zones:\n", opp[["area", "mean_rate", "n_events", "top_type"]].to_string(index=False))
    print(f"\nWrote {OUTPUT}")
    if not args.no_open:
        webbrowser.open(OUTPUT.as_uri())


if __name__ == "__main__":
    main()
