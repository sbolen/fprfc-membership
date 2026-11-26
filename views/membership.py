"""FPRFC membership dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from common import (
    BG, BAR_TRACK, CARD_BG, CARD_BORDER, CONTROL_COLOR, FOUNDERS, FOUNDERS_COLOR,
    GRID, MAP_SCALE, MUTED, NEUTRAL_TINT, REVENUE_CHART_COLORS, REVENUE_COLOR,
    ROOTS, ROOTS_COLOR, STYLE, TIER_COLORS, TOTAL_COLOR,
    chart_layout, fdate, header_html, human, logo_data_uri, pct, stamp,
)

BASE = Path(__file__).resolve().parent.parent
DATA_PATH = BASE / "data" / "2026-memberships.csv"
GEO_PATH = BASE / "data" / "geo_lookup.csv"
LOGO_PATH = BASE / "assets" / "logo.png"

# Reference point for the distance metric. Members' locations are approximated by
# postcode centroid (US) or city (international) since street addresses were removed.
# The headline names the landmark; the note gives the street address it sits on.
REFERENCE_HEADLINE = "Average Distance from Gateway Arch"
REFERENCE_ADDRESS = "100 Washington Avenue, St. Louis, MO"
REFERENCE_NOTE = f"straight-line distance from {REFERENCE_ADDRESS}"
REFERENCE_LATLON = (38.6245067, -90.1856833)
EARTH_RADIUS_MI = 3958.7613

# Landmarks for the distance-band analysis, measured over the MO + IL membership base.
LANDMARKS = [
    ("Bishop DuBourg", "5850 Eichelberger St, St. Louis, MO 63109", (38.5808670, -90.2957539)),
    ("Rockwell Beer", "1320 S Vandeventer Ave, St. Louis, MO 63110", (38.6256886, -90.2514078)),
]
DISTANCE_BANDS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
MAP_ZOOM = 8
MAP_CENTER = (38.627, -90.199)   # downtown St. Louis, so the bands stay framed

# st.map takes literal colours rather than categories, and centres on the data's
# bounding box — which the Chicago/Kansas City members pull well north-west of
# St. Louis. The map is therefore built with pydeck (the engine st.map wraps) so the
# view can be pinned and the marker sizes controlled.
MAP_MEMBER_COLOR = CONTROL_COLOR
MAP_LANDMARK_COLORS = [ROOTS_COLOR, FOUNDERS_COLOR]
MAP_MEMBER_RGB = [2, 70, 58, 190]
MAP_LANDMARK_RGB = [[155, 34, 70, 235], [219, 88, 46, 235]]

TIER_PRICES = {ROOTS: 25, FOUNDERS: 314}

COUNTRY_NAMES = {
    "US": "United States",
    "CA": "Canada",
    "DE": "Germany",
    "JP": "Japan",
    "TW": "Taiwan",
    "VN": "Vietnam",
    "HR": "Croatia",
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_data(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path)

    for col in ("City", "State Code", "Country Code", "Item Name", "Status"):
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Order dates arrive in two formats; parse each and combine.
    parsed = pd.to_datetime(df["Order Date"], format="%m/%d/%Y %H:%M", errors="coerce")
    alt = pd.to_datetime(df["Order Date"], format="%Y-%m-%d %H:%M", errors="coerce")
    df["Order Date"] = parsed.fillna(alt)
    df = df.dropna(subset=["Order Date"])

    df["Tier"] = df["Item Name"].map(
        {"Roots of the Club Membership": ROOTS, "Founders Ring Membership": FOUNDERS}
    ).fillna(df["Item Name"])

    country = df["Country Code"].str.upper()
    country = country.replace({"UNITED STATES": "US", "USA": "US"})
    df["CountryISO"] = country
    df["Country"] = country.map(lambda c: COUNTRY_NAMES.get(c, c))

    state = df["State Code"].str.strip().str.upper()
    df["State"] = state.where(state.isin(US_STATES), "")
    df["IsUS"] = df["CountryISO"] == "US"

    df["Canceled"] = df["Status"].str.lower().eq("canceled")

    # "Item #" in the export is the quantity purchased for that line item.
    df["Qty"] = pd.to_numeric(df["Item #"], errors="coerce").fillna(1).clip(lower=1).astype(int)
    df["Revenue"] = df["Qty"] * df["Tier"].map(TIER_PRICES)

    # Location key for the offline geocode lookup: postcode for the US (ZIP+4 trimmed),
    # otherwise city. Street addresses were removed from the export, so this is the
    # finest granularity available.
    zip5 = df["Postcode"].str.split("-").str[0]
    df["GeoKey"] = df["CountryISO"] + "|" + zip5.where(df["IsUS"], df["City"].str.upper())
    return df.sort_values("Order Date").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_geo(path: str, mtime: float) -> dict[str, tuple[float, float]]:
    """Offline lookup of location key -> (lat, lon). Regenerate with build_geo_lookup.py."""
    geo = pd.read_csv(path)
    return {f"{r.country}|{r.key}": (float(r.lat), float(r.lon)) for r in geo.itertuples()}


def distance_miles(a: tuple[float, float], b: tuple[float, float] | None) -> float | None:
    """Great-circle (straight-line) distance in miles, or None if b is unknown."""
    if b is None or any(pd.isna(x) for x in (*a, *b)):
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #

data_mtime = DATA_PATH.stat().st_mtime
df_all = load_data(str(DATA_PATH), data_mtime)

# ------------------------------- sidebar ----------------------------------- #
with st.sidebar:
    st.markdown('<div class="eyebrow">Filters</div>', unsafe_allow_html=True)

    include_canceled = st.toggle("Include canceled orders", value=False)
    tiers = st.multiselect("Membership", [ROOTS, FOUNDERS], default=[ROOTS, FOUNDERS])

    min_date = df_all["Order Date"].min().date()
    max_date = df_all["Order Date"].max().date()
    date_range = st.slider("Order date", min_value=min_date, max_value=max_date,
                           value=(min_date, max_date), format="MMM D, YYYY")

df = df_all[~df_all["Canceled"]] if not include_canceled else df_all.copy()
df = df[df["Tier"].isin(tiers)]
df = df[(df["Order Date"].dt.date >= date_range[0]) & (df["Order Date"].dt.date <= date_range[1])].copy()

# Straight-line distance from the reference address, via the offline geocode lookup.
# Members' locations are postcode centroids (US) or city centroids (international).
geo_lookup = load_geo(str(GEO_PATH), GEO_PATH.stat().st_mtime)
df["Distance"] = [distance_miles(REFERENCE_LATLON, geo_lookup.get(k)) for k in df["GeoKey"]]

if df.empty:
    st.title("Membership Dashboard")
    st.info("No memberships match the current filters.")
    st.stop()

n_orders = len(df)
n_total = int(df["Qty"].sum())
n_roots = int(df.loc[df["Tier"] == ROOTS, "Qty"].sum())
n_founders = int(df.loc[df["Tier"] == FOUNDERS, "Qty"].sum())

last_day = df["Order Date"].max().normalize()
recent = int(df.loc[df["Order Date"] > last_day - pd.Timedelta(days=30), "Qty"].sum())

with st.sidebar:
    st.divider()
    st.download_button(
        "Download filtered data",
        data=df.drop(columns=["IsUS", "Canceled", "Qty"])
              .rename(columns={"Item #": "Quantity"})
              .to_csv(index=False).encode("utf-8"),
        file_name="memberships-filtered.csv",
        mime="text/csv",
        width="stretch",
    )
    st.caption(f"{human(n_total)} memberships from {human(n_orders)} orders · "
               f"data through {fdate(df_all['Order Date'].max())}")

# -------------------------------- header ----------------------------------- #
logo_uri = logo_data_uri(str(LOGO_PATH), LOGO_PATH.stat().st_mtime)

st.markdown(
    header_html(
        logo_uri,
        eyebrow="FPRFC · 2026",
        title="Membership Dashboard",
        stamp_value=stamp(data_mtime),
        stamp_sub=f"data through {fdate(df_all['Order Date'].max())}",
    ),
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="subtitle">{human(n_total)} memberships from {human(n_orders)} orders · '
    f'{fdate(df["Order Date"].min())} – {fdate(df["Order Date"].max())}</div>',
    unsafe_allow_html=True,
)

# ---------------------------- top-line numbers ----------------------------- #
n_countries = df["Country"].nunique()
n_intl = n_total - int(df.loc[df["IsUS"], "Qty"].sum())

n_revenue = float(df["Revenue"].sum())
founders_revenue = float(df.loc[df["Tier"] == FOUNDERS, "Revenue"].sum())
days_span = max((df["Order Date"].max().normalize() - df["Order Date"].min().normalize()).days + 1, 1)
avg_per_day = n_total / days_span

# Distance stats (weighted by quantity, so a 2-membership order counts twice).
geo_ok = df["Distance"].notna()
dist_units = int(df.loc[geo_ok, "Qty"].sum())


def weighted_mean(sub: pd.DataFrame) -> float | None:
    if sub.empty or sub["Qty"].sum() == 0:
        return None
    return float((sub["Distance"] * sub["Qty"]).sum() / sub["Qty"].sum())


dist_mean = weighted_mean(df[geo_ok])
dist_us_mean = weighted_mean(df[geo_ok & df["IsUS"]])
dist_median = float(df.loc[geo_ok, "Distance"].median()) if geo_ok.any() else None
dist_max = float(df.loc[geo_ok, "Distance"].max()) if geo_ok.any() else None
dist_max_city = df.loc[df["Distance"].idxmax(), "City"] if geo_ok.any() else ""


def mi(v: float | None) -> str:
    return f"{v:,.0f} mi" if v is not None else "—"


dist_note = (f"{REFERENCE_NOTE}" if dist_units == n_total
             else f"{REFERENCE_NOTE} · {dist_units} of {n_total} located")

st.markdown(
    f"""
    <div class="cards">
      <div class="card accent-total">
        <div class="label">Total memberships</div>
        <div class="value">{human(n_total)}</div>
        <div class="note">{recent} in the last 30 days</div>
      </div>
      <div class="card accent-revenue">
        <div class="label">Total revenue</div>
        <div class="value">${n_revenue:,.0f}</div>
        <div class="note">{pct(founders_revenue, n_revenue)} from Founders Ring</div>
      </div>
      <div class="card accent-rate">
        <div class="label">Avg new members / day</div>
        <div class="value">{avg_per_day:.1f}</div>
        <div class="note">{human(n_total)} over {days_span:,} days</div>
      </div>
      <div class="card accent-roots">
        <div class="label">Roots of the Club</div>
        <div class="value">{human(n_roots)}</div>
        <div class="note">{pct(n_roots, n_total)} of memberships</div>
        <div class="bar"><span style="width:{100 * n_roots / n_total:.1f}%; background:{TIER_COLORS[ROOTS]};"></span></div>
      </div>
      <div class="card accent-founders">
        <div class="label">Founders Ring</div>
        <div class="value">{human(n_founders)}</div>
        <div class="note">{pct(n_founders, n_total)} of memberships</div>
        <div class="bar"><span style="width:{100 * n_founders / n_total:.1f}%; background:{TIER_COLORS[FOUNDERS]};"></span></div>
      </div>
      <div class="card accent-world">
        <div class="label">Countries</div>
        <div class="value">{n_countries}</div>
        <div class="note">{human(n_intl)} international members</div>
      </div>
      <div class="card card-wide accent-distance">
        <div class="wide-main">
          <div class="label">{REFERENCE_HEADLINE}</div>
          <div class="value">{mi(dist_mean)}</div>
          <div class="note">{dist_note}</div>
        </div>
        <div class="mini">
          <div><div class="k">US members</div><div class="v">{mi(dist_us_mean)}</div></div>
          <div><div class="k">Median</div><div class="v">{mi(dist_median)}</div></div>
          <div><div class="k">Furthest</div><div class="v">{mi(dist_max)}</div><div class="s">{dist_max_city}</div></div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ------------------------------ growth chart ------------------------------- #
st.markdown('<div class="section-title">Growth over time</div>', unsafe_allow_html=True)

sub_slot = st.empty()
mc, vc = st.columns([1, 1], gap="small")
with mc:
    metric = st.segmented_control(
        "Metric", ["Memberships", "Revenue"], default="Memberships",
        label_visibility="collapsed",
    ) or "Memberships"
with vc:
    mode = st.segmented_control(
        "Growth view", ["Cumulative", "New per week"], default="Cumulative",
        label_visibility="collapsed",
    ) or "Cumulative"

is_revenue = metric == "Revenue"
value_col = "Revenue" if is_revenue else "Qty"
total_value = float(df[value_col].sum())

if is_revenue:
    sub_text = f'{"Cumulative revenue" if mode == "Cumulative" else "New revenue per week"}'
    sub_tail = f' · <b>${total_value:,.0f}</b> total'
else:
    sub_text = f'{"Cumulative membership count" if mode == "Cumulative" else "New memberships per week"}'
    sub_tail = f' · <b>{total_value:,.0f}</b> total'

sub_slot.markdown(
    f'<div class="section-sub">{sub_text} · '
    f'{fdate(df["Order Date"].min())} to {fdate(df["Order Date"].max())}{sub_tail}</div>',
    unsafe_allow_html=True,
)

daily = (df.groupby([df["Order Date"].dt.normalize(), "Tier"])[value_col].sum()
           .unstack(fill_value=0).sort_index())
daily = daily.reindex(columns=[ROOTS, FOUNDERS], fill_value=0)

axis_cfg = dict(tickprefix="$", tickformat=",.0f") if is_revenue else dict(tickformat=",")
hover_fmt = "$%{y:,.0f}" if is_revenue else "%{y:,}"

fig = go.Figure()
chart_colors = REVENUE_CHART_COLORS if is_revenue else TIER_COLORS
if mode == "Cumulative":
    cumulative = daily.cumsum()
    for tier in (ROOTS, FOUNDERS):
        fig.add_trace(go.Scatter(
            x=cumulative.index, y=cumulative[tier], name=tier, mode="lines",
            line=dict(color=chart_colors[tier], width=2.6),
            hovertemplate=tier + ": " + hover_fmt + "<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=cumulative.index, y=cumulative.sum(axis=1),
        name="All revenue" if is_revenue else "All memberships", mode="lines",
        line=dict(color=CONTROL_COLOR, width=1.6, dash="dot"),
        hovertemplate="All: " + hover_fmt + "<extra></extra>",
    ))
    fig.update_yaxes(title=None, rangemode="tozero", **axis_cfg)
else:
    weekly = daily.resample("W-MON").sum()
    for tier in (ROOTS, FOUNDERS):
        fig.add_trace(go.Bar(
            x=weekly.index, y=weekly[tier], name=tier,
            marker=dict(color=chart_colors[tier], line=dict(width=0)),
            hovertemplate=tier + ": " + hover_fmt + "<extra></extra>",
        ))
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_yaxes(title=None, **axis_cfg)

fig.update_layout(hovermode="x unified")
st.plotly_chart(chart_layout(fig, height=380), width="stretch", config={"displayModeBar": False})

# ------------------------------ geography ---------------------------------- #
us = df[df["IsUS"] & df["State"].ne("")]

st.write("")
st.markdown('<div class="section-title">Where members are</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">Breakdown by US state and by country</div>',
    unsafe_allow_html=True,
)

head_l, head_m, head_r = st.columns([2, 1, 1], gap="small")
with head_l:
    st.markdown(
        '<div class="subhead">By state <span class="hint">· US</span></div>',
        unsafe_allow_html=True,
    )
with head_m:
    state_metric = st.segmented_control(
        "State metric", ["Members", "Revenue"], default="Members",
        label_visibility="collapsed",
    ) or "Members"
with head_r:
    view = st.segmented_control("State view", ["Bar", "Map"], default="Bar",
                                label_visibility="collapsed") or "Bar"

state_revenue = state_metric == "Revenue"
state_col = "Revenue" if state_revenue else "Qty"
by_state = us.groupby("State")[state_col].sum().sort_values(ascending=False)
state_total = float(by_state.sum())
state_unit = "US revenue" if state_revenue else "US members"
state_total_label = f"${state_total:,.0f}" if state_revenue else f"{state_total:,.0f}"
state_hover = "$%{x:,.0f}" if state_revenue else "%{x:,} members"

if by_state.empty:
    st.info("No US memberships in the current selection.")
elif view == "Map":
    sdata = by_state.rename_axis("state").reset_index(name="value")
    sdata["logz"] = sdata["value"].map(math.log10)
    base_ticks = ([25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000]
                  if state_revenue else [1, 2, 5, 10, 25, 50, 100, 350])
    ticks = [t for t in base_ticks if t <= sdata["value"].max()]
    tickvals = [math.log10(t) for t in ticks]
    ticktext = [f"${t:,.0f}" if state_revenue else f"{t:,}" for t in ticks]
    map_hover = ("%{location}<br>$%{customdata:,.0f} revenue<extra></extra>"
                 if state_revenue else "%{location}<br>%{customdata:,} members<extra></extra>")
    m = go.Figure(go.Choropleth(
        locations=sdata["state"], z=sdata["logz"], customdata=sdata["value"],
        locationmode="USA-states",
        colorscale=MAP_SCALE,
        marker_line_color=BG, marker_line_width=0.8,
        zmin=0, zmax=sdata["logz"].max(),
        colorbar=dict(title=dict(text="Revenue" if state_revenue else "Members",
                                 font=dict(size=11)),
                      thickness=10, len=0.62, y=0.5, outlinewidth=0,
                      tickvals=tickvals, ticktext=ticktext, tickfont=dict(size=10)),
        hovertemplate=map_hover,
    ))
    m.update_layout(geo=dict(scope="usa", bgcolor="rgba(0,0,0,0)",
                             landcolor="#f3ece0", lakecolor="rgba(0,0,0,0)",
                             subunitcolor=BG))
    m.update_geos(showlakes=False, showsubunits=True, showframe=False)
    st.plotly_chart(chart_layout(m, height=390),
                    width="stretch", config={"displayModeBar": False})
    st.caption(
        f"{state_total_label} {state_unit} across {len(by_state)} states · "
        f"{pct(by_state.iloc[0], state_total)} in {by_state.index[0]} · log color scale"
    )
else:
    top = by_state.head(12).sort_values()
    bar = go.Figure(go.Bar(
        y=top.index, x=top.values, orientation="h",
        marker=dict(color=REVENUE_COLOR if state_revenue else CONTROL_COLOR,
                    line=dict(width=0)),
        text=[f"${v:,.0f}" if state_revenue else f"{v:,.0f}" for v in top.values],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: " + state_hover + "<extra></extra>",
    ))
    bar.update_xaxes(showgrid=True, gridcolor=GRID, showticklabels=False, ticks="",
                     range=[0, top.max() * (1.22 if state_revenue else 1.14)])
    bar.update_yaxes(showgrid=False, ticks="")
    bar.update_layout(showlegend=False)
    st.plotly_chart(chart_layout(bar, height=330), width="stretch",
                    config={"displayModeBar": False})
    st.caption(
        f"{state_total_label} {state_unit} across {len(by_state)} states · "
        f"{pct(by_state.iloc[0], state_total)} in {by_state.index[0]}"
    )

st.write("")
st.markdown(
    '<div class="subhead">By country <span class="hint">· all members</span></div>',
    unsafe_allow_html=True,
)

by_country = df.groupby("Country")["Qty"].sum().sort_values(ascending=False)
order = list(by_country.sort_values().index)
colors = [NEUTRAL_TINT if c != "United States" else CONTROL_COLOR for c in order]
cfig = go.Figure(go.Bar(
    y=order, x=by_country.reindex(order).values, orientation="h",
    marker=dict(color=colors, line=dict(width=0)),
    text=by_country.reindex(order).values, textposition="outside", cliponaxis=False,
    hovertemplate="%{y}: %{x:,} members<extra></extra>",
))
cfig.update_xaxes(showgrid=True, gridcolor=GRID, showticklabels=False, ticks="",
                  range=[0, by_country.max() * 1.14])
cfig.update_yaxes(showgrid=False, ticks="")
cfig.update_layout(showlegend=False)
st.plotly_chart(chart_layout(cfig, height=290), width="stretch",
                config={"displayModeBar": False})
st.caption(
    f"{pct(by_country.get('United States', 0), n_total)} of members in the US · "
    f"{human(n_intl)} across {max(n_countries - 1, 0)} other countries"
)

# ------------------- distance from St. Louis landmarks --------------------- #
st.write("")
st.markdown('<div class="section-title">Proximity to Club Landmarks</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">Missouri and Illinois members, cumulative counts by '
    'straight-line distance from each landmark</div>',
    unsafe_allow_html=True,
)

mo_il = df[df["State"].isin(["MO", "IL"])].copy()
dist_cols = []
for name, _addr, latlon in LANDMARKS:
    col = f"dist::{name}"
    dist_cols.append(col)
    mo_il[col] = [distance_miles(latlon, geo_lookup.get(k)) for k in mo_il["GeoKey"]]

mo_il_units = int(mo_il["Qty"].sum())
furthest_band = DISTANCE_BANDS[-1]

if mo_il.empty:
    st.info("No Missouri or Illinois memberships in the current selection.")
else:
    nearest = mo_il[dist_cols].min(axis=1)
    beyond = int(mo_il.loc[nearest > furthest_band, "Qty"].sum())

    mcol, tcol = st.columns([2.2, 1], gap="large")

    with mcol:
        members = pd.DataFrame(
            [(lat, lon, "Member (MO & IL)") for lat, lon in
             (geo_lookup[k] for k in mo_il["GeoKey"])],
            columns=["lat", "lon", "label"],
        )

        def scatter(data, fill, radius, min_px, max_px):
            return pdk.Layer(
                "ScatterplotLayer", data=data, get_position=["lon", "lat"],
                get_fill_color=fill, get_radius=radius,
                radius_min_pixels=min_px, radius_max_pixels=max_px, pickable=True,
            )

        layers = [scatter(members, MAP_MEMBER_RGB, 500, 4, 9)]
        for (name, address, latlon), rgb in zip(LANDMARKS, MAP_LANDMARK_RGB):
            layers.append(scatter(
                pd.DataFrame([{"lat": latlon[0], "lon": latlon[1],
                               "label": f"{name} — {address}"}]),
                rgb, 1200, 9, 16,
            ))

        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(
                    latitude=MAP_CENTER[0], longitude=MAP_CENTER[1], zoom=MAP_ZOOM, pitch=0
                ),
                map_style="light",
                tooltip={"html": "<b>{label}</b>", "style": {"fontSize": "12px"}},
            ),
            height=520, width="stretch",
        )

        legend = "".join(
            f'<span><i style="background:{color}"></i>{name}</span>'
            for name, color in [("Members (MO & IL)", MAP_MEMBER_COLOR)]
            + [(n, c) for (n, _a, _l), c in zip(LANDMARKS, MAP_LANDMARK_COLORS)]
        )
        st.markdown(f'<div class="map-legend">{legend}</div>', unsafe_allow_html=True)
        st.caption(
            f"{human(mo_il_units)} memberships across "
            f"{mo_il['State'].nunique()} states · "
            f"{human(mo_il_units - beyond)} within {furthest_band} mi of a landmark · "
            f"zoom {MAP_ZOOM} on St. Louis — drag or scroll to change the view"
        )

    with tcol:
        header = "".join(f"<th>{name}</th>" for name, _a, _l in LANDMARKS)
        body = ""
        for band in DISTANCE_BANDS:
            cells = "".join(
                f"<td>{human(int(mo_il.loc[mo_il[col] <= band, 'Qty'].sum()))}</td>"
                for col in dist_cols
            )
            body += f"<tr><td>{band} mi</td>{cells}</tr>"
        st.markdown(
            f'<table class="bands"><thead><tr><th>Within</th>{header}</tr></thead>'
            f"<tbody>{body}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.caption("Cumulative — each figure includes everyone closer in.")


# -------------------------------- footer ----------------------------------- #
st.write("")
with st.expander("About this data"):
    st.markdown(
        f"""
Source: `data/2026-memberships.csv` · {len(df_all):,} order records · {int(df_all["Qty"].sum()):,} memberships.

- `Item #` is the quantity purchased. {int((df_all["Qty"] > 1).sum())} orders have quantity 2, so every
  count on this page sums quantity rather than rows: {int(df_all["Qty"].sum()):,} units from {len(df_all):,} orders.
- Active split: {int(df_all.loc[~df_all["Canceled"] & (df_all["Tier"] == ROOTS), "Qty"].sum()):,} Roots +
  {int(df_all.loc[~df_all["Canceled"] & (df_all["Tier"] == FOUNDERS), "Qty"].sum()):,} Founders =
  {int(df_all.loc[~df_all["Canceled"], "Qty"].sum()):,} memberships.
- This export is de-identified: first name, last name, street address, email and customer
  note have been removed. City, state and postcode are retained.
- Repeat purchases are counted separately (e.g. one member with three orders), but without
  an email column the dashboard can no longer tell repeat buyers apart.
- Average new members per day is the filtered membership count divided by the number of
  days from the first to the last order in the current selection.
- Average distance is straight-line (great-circle) from {REFERENCE_ADDRESS}. Because street
  addresses were removed, each member's location is approximated by their postcode
  centroid (US, from GeoNames) or city centroid (international, from OpenStreetMap) — so
  treat it as indicative, not exact. Averages are weighted by quantity, so a
  two-membership order counts twice. The lookup lives in `data/geo_lookup.csv`; rerun
  `build_geo_lookup.py` after adding an export with new postcodes.
- The landmark section counts Missouri and Illinois memberships within 5–50 mi
  (straight-line) of Bishop DuBourg High School and Rockwell Beer. The map uses pydeck
  rather than `st.map` because `st.map` centres on the data's bounding box, which the
  Chicago and Kansas City members pull well away from St. Louis; pydeck pins the view and
  controls marker size.
- Country values are normalized (e.g. `US` / `United States` → United States); state
  abbreviations are cleaned and non-US regions are excluded from the state view.
- Canceled orders are excluded by default ({int(df_all["Canceled"].sum())} in the file).
- Revenue uses list prices of {int(TIER_PRICES[ROOTS])} for Roots of the Club and
  {int(TIER_PRICES[FOUNDERS])} for Founders Ring, so it reflects gross membership sales,
  not refunds or fees.
        """
    )
