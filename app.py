"""FPRFC membership dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import base64
import math
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "2026-memberships.csv"
LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"

ROOTS = "Roots of the Club"
FOUNDERS = "Founders Ring"

# Brand palette.
BG = "#faf1e0"            # page background
REVENUE_COLOR = "#008758"  # anything revenue-related
ROOTS_COLOR = "#9b2246"    # Roots of the Club
FOUNDERS_COLOR = "#db582e"  # Founders Ring
CONTROL_COLOR = "#02463a"  # toggles, buttons, map gradient, aggregate metrics

TIER_COLORS = {ROOTS: ROOTS_COLOR, FOUNDERS: FOUNDERS_COLOR}

# Revenue charts stay in the revenue green; the tier split uses a lighter tint of
# the same hue. Neutral charts use the control green with a tint for the "other" group.
REVENUE_CHART_COLORS = {ROOTS: REVENUE_COLOR, FOUNDERS: "#8cc9b4"}
NEUTRAL_TINT = "#7ba394"

CARD_BG = "#fffcf4"
CARD_BORDER = "#ecdfc7"
BAR_TRACK = "#f2e8d5"
TOTAL_COLOR = CONTROL_COLOR
MUTED = "#8a7a63"
GRID = "#e8dcc4"

# Light-to-dark green ramp ending on the control colour, for the map gradient.
MAP_SCALE = [[0, "#f1efe2"], [0.35, "#9dc3b2"], [0.7, "#3f8a72"], [1, CONTROL_COLOR]]
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
    df["Country"] = country.map(lambda c: COUNTRY_NAMES.get(c, c))

    state = df["State Code"].str.strip().str.upper()
    df["State"] = state.where(state.isin(US_STATES), "")
    df["IsUS"] = df["Country"] == "United States"

    df["Canceled"] = df["Status"].str.lower().eq("canceled")

    # "Item #" in the export is the quantity purchased for that line item.
    df["Qty"] = pd.to_numeric(df["Item #"], errors="coerce").fillna(1).clip(lower=1).astype(int)
    df["Revenue"] = df["Qty"] * df["Tier"].map(TIER_PRICES)
    return df.sort_values("Order Date").reset_index(drop=True)


def chart_layout(fig: go.Figure, height: int = 340, **kwargs) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", size=13, color="#6f6350"),
        hoverlabel=dict(bgcolor=CONTROL_COLOR, font_color="#ffffff", bordercolor=CONTROL_COLOR),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12)),
        **kwargs,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=GRID, ticks="outside", tickcolor=GRID)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, ticks="")
    return fig


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def pct(part: float, whole: float) -> str:
    return f"{(100 * part / whole) if whole else 0:.1f}%"


def human(n: int) -> str:
    return f"{n:,}"


def fdate(ts: pd.Timestamp) -> str:
    return f"{ts:%b} {ts.day}, {ts.year}"


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="FPRFC Membership", page_icon=str(LOGO_PATH), layout="wide")

st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif; }}
        .block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1220px; }}
        .block-container h1 {{ font-size: 2.1rem; line-height: 1.2; letter-spacing: -0.025em;
                              color: {TOTAL_COLOR}; margin-bottom: 0.1rem; }}
        h1 {{ font-size: 2.1rem; }}
        .eyebrow {{ text-transform: uppercase; letter-spacing: 0.14em; font-size: 0.7rem;
                    font-weight: 600; color: {MUTED}; margin-bottom: 0.35rem; }}
        .header {{ display: flex; align-items: center; gap: 1.05rem; margin-bottom: 0.2rem; }}
        .header .crest {{ height: 78px; width: 78px; display: block; flex: 0 0 auto; }}
        .header .header-text {{ min-width: 0; }}
        .header h1 {{ margin: 0; }}
        @media (max-width: 620px) {{ .header .crest {{ height: 58px; width: 58px; }} }}

        .subtitle {{ color: {MUTED}; font-size: 0.92rem; margin-bottom: 1.6rem; }}
        .section-title {{ font-size: 1.05rem; font-weight: 600; color: {TOTAL_COLOR};
                          letter-spacing: -0.01em; margin-bottom: 0.15rem; }}
        .section-sub {{ color: {MUTED}; font-size: 0.82rem; margin-bottom: 0.6rem; }}

        .card {{ background: {CARD_BG}; border: 1px solid {CARD_BORDER}; border-radius: 12px;
                 padding: 1rem 1.1rem 0.95rem 1.1rem; height: 100%; }}
        .card .label {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.09em;
                        text-transform: uppercase; color: {MUTED}; white-space: nowrap;
                        overflow: hidden; text-overflow: ellipsis; }}
        .card .value {{ font-size: 1.9rem; font-weight: 700; line-height: 1.15; color: {TOTAL_COLOR};
                        letter-spacing: -0.03em; margin-top: 0.25rem; }}
        .card .note {{ font-size: 0.78rem; color: {MUTED}; margin-top: 0.1rem; }}
        .cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.7rem; }}
        @media (max-width: 1100px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
        @media (max-width: 620px) {{ .cards {{ grid-template-columns: 1fr; }} }}
        .bar {{ height: 4px; border-radius: 2px; background: {BAR_TRACK}; margin-top: 0.7rem; overflow: hidden; }}
        .bar > span {{ display: block; height: 100%; border-radius: 2px; }}
        .accent-total {{ border-left: 3px solid {CONTROL_COLOR}; }}
        .accent-revenue {{ border-left: 3px solid {REVENUE_COLOR}; }}
        .accent-rate {{ border-left: 3px solid {CONTROL_COLOR}; }}
        .accent-roots {{ border-left: 3px solid {ROOTS_COLOR}; }}
        .accent-founders {{ border-left: 3px solid {FOUNDERS_COLOR}; }}
        .accent-world {{ border-left: 3px solid {CONTROL_COLOR}; }}

        .subhead {{ font-size: 0.95rem; font-weight: 600; color: {TOTAL_COLOR}; }}
        .hint {{ color: {MUTED}; font-weight: 400; font-size: 0.8rem; }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px; }}
        [data-testid="stSidebar"] .block-container {{ padding-top: 1.5rem; }}
        [data-testid="stHeaderActionElements"] {{ display: none; }}
        footer, #MainMenu {{ visibility: hidden; }}
    </style>
    """,
    unsafe_allow_html=True,
)

df_all = load_data(str(DATA_PATH), DATA_PATH.stat().st_mtime)

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
df = df[(df["Order Date"].dt.date >= date_range[0]) & (df["Order Date"].dt.date <= date_range[1])]

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
@st.cache_data(show_spinner=False)
def _logo_uri(path: str, mtime: float) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


logo_uri = _logo_uri(str(LOGO_PATH), LOGO_PATH.stat().st_mtime)

st.markdown(
    f"""
    <div class="header">
      <img class="crest" src="{logo_uri}" alt="FPRFC crest" />
      <div class="header-text">
        <div class="eyebrow">FPRFC · 2026</div>
        <h1>Membership Dashboard</h1>
      </div>
    </div>
    """,
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
- This export is de-identified: first name, last name, street address and email have been
  removed. City, state and postcode are retained.
- Repeat purchases are counted separately (e.g. one member with three orders), but without
  an email column the dashboard can no longer tell repeat buyers apart.
- Average new members per day is the filtered membership count divided by the number of
  days from the first to the last order in the current selection.
- Country values are normalized (e.g. `US` / `United States` → United States); state
  abbreviations are cleaned and non-US regions are excluded from the state view.
- Canceled orders are excluded by default ({int(df_all["Canceled"].sum())} in the file).
- Revenue uses list prices of {int(TIER_PRICES[ROOTS])} for Roots of the Club and
  {int(TIER_PRICES[FOUNDERS])} for Founders Ring, so it reflects gross membership sales,
  not refunds or fees.
        """
    )
