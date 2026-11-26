"""Palette, formatting helpers and page styling shared by every page.

Kept separate from the page scripts so the membership page and the merchandise page
render with the same type scale, cards and colours.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go

# --------------------------------------------------------------------------- #
# Brand palette
# --------------------------------------------------------------------------- #
BG = "#faf1e0"             # page background
REVENUE_COLOR = "#008758"  # anything revenue-related
ROOTS_COLOR = "#9b2246"    # Roots of the Club
FOUNDERS_COLOR = "#db582e"  # Founders Ring
CONTROL_COLOR = "#02463a"  # toggles, buttons, map gradient, aggregate metrics

CARD_BG = "#fffcf4"
CARD_BORDER = "#ecdfc7"
BAR_TRACK = "#f2e8d5"
TOTAL_COLOR = CONTROL_COLOR
MUTED = "#8a7a63"
GRID = "#e8dcc4"
NEUTRAL_TINT = "#7ba394"

# Light-to-dark green ramp ending on the control colour, for the map gradient.
MAP_SCALE = [[0, "#f1efe2"], [0.35, "#9dc3b2"], [0.7, "#3f8a72"], [1, CONTROL_COLOR]]

ROOTS = "Roots of the Club"
FOUNDERS = "Founders Ring"
TIER_COLORS = {ROOTS: ROOTS_COLOR, FOUNDERS: FOUNDERS_COLOR}

# Revenue charts stay in the revenue green; the tier split uses a lighter tint of the
# same hue. Neutral charts use the control green with a tint for the "other" group.
REVENUE_CHART_COLORS = {ROOTS: REVENUE_COLOR, FOUNDERS: "#8cc9b4"}

# Timestamps display in the club's local time, whatever timezone the host runs in.
# Streamlit Community Cloud runs in UTC, so without this the stamp would read in UTC.
DISPLAY_TZ_NAME = "America/Chicago"
try:
    DISPLAY_TZ = ZoneInfo(DISPLAY_TZ_NAME)
except Exception:  # tz database unavailable on the host -> fall back to UTC
    DISPLAY_TZ = timezone.utc


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def pct(part: float, whole: float) -> str:
    return f"{(100 * part / whole) if whole else 0:.1f}%"


def human(n: int) -> str:
    return f"{n:,}"


def money(v: float) -> str:
    return f"${v:,.2f}"


def fdate(ts: pd.Timestamp) -> str:
    return f"{ts:%b} {ts.day}, {ts.year}"


def stamp(ts: float) -> str:
    """Human-readable 'last updated' text from a file mtime, in the club's timezone."""
    dt = datetime.fromtimestamp(ts, tz=DISPLAY_TZ)
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt:%b} {dt.day}, {dt.year} · {hour}:{dt.minute:02d} {ampm} {dt.tzname()}"


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
# Chrome
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=4)
def logo_data_uri(path: str, mtime: float) -> str:
    """Inline the crest so the header does not depend on static file serving."""
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def header_html(logo_uri: str, eyebrow: str, title: str,
                stamp_value: str, stamp_sub: str) -> str:
    return f"""
    <div class="header">
      <img class="crest" src="{logo_uri}" alt="FPRFC crest" />
      <div class="header-text">
        <div class="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
      </div>
      <div class="stamp">
        <div class="eyebrow">Last updated</div>
        <div class="stamp-value">{stamp_value}</div>
        <div class="stamp-sub">{stamp_sub}</div>
      </div>
    </div>
    """


STYLE = f"""
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
    .header h1 {{ margin: 0; overflow-wrap: normal; word-break: normal; }}
    .header .stamp {{ margin-left: auto; text-align: right; flex: 0 0 auto; padding-left: 1rem; }}
    .header .stamp .eyebrow {{ margin-bottom: 0.15rem; }}
    .stamp-value {{ font-size: 0.86rem; font-weight: 600; color: {TOTAL_COLOR}; white-space: nowrap; }}
    .stamp-sub {{ font-size: 0.75rem; color: {MUTED}; margin-top: 0.1rem; white-space: nowrap; }}
    /* Below this width the sidebar leaves too little room for the title and stamp
       side by side, so the stamp drops onto its own line. */
    @media (max-width: 1150px) {{
        .header {{ flex-wrap: wrap; }}
        .header .stamp {{ flex-basis: 100%; margin-left: 0; text-align: left;
                          padding-left: 0; margin-top: 0.6rem; }}
        .header h1 {{ font-size: 1.8rem; }}
    }}
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

    /* Wide card: headline figure on the left, supporting stats on the right. */
    .card-wide {{ grid-column: 1 / -1; display: flex; align-items: center;
                  gap: 1.5rem 2.5rem; flex-wrap: wrap; }}
    .card-wide .wide-main {{ min-width: 220px; }}
    .mini {{ display: flex; gap: 2.2rem; margin-left: auto; flex-wrap: wrap; }}
    .mini > div {{ text-align: right; }}
    .mini .k {{ font-size: 0.68rem; font-weight: 600; letter-spacing: 0.09em;
                text-transform: uppercase; color: {MUTED}; white-space: nowrap; }}
    .mini .v {{ font-size: 1.15rem; font-weight: 600; color: {TOTAL_COLOR}; margin-top: 0.15rem; }}
    .mini .s {{ font-size: 0.72rem; color: {MUTED}; margin-top: 0.1rem; }}

    /* Cumulative distance-band table */
    table.bands {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    table.bands th {{ font-size: 0.66rem; font-weight: 600; letter-spacing: 0.08em;
                      text-transform: uppercase; color: {MUTED}; text-align: right;
                      padding: 0 0.5rem 0.45rem 0.5rem;
                      border-bottom: 1px solid {CARD_BORDER}; white-space: nowrap; }}
    table.bands th:first-child {{ text-align: left; }}
    table.bands td {{ text-align: right; padding: 0.34rem 0.5rem; color: {TOTAL_COLOR};
                      border-bottom: 1px solid {GRID}; font-variant-numeric: tabular-nums; }}
    table.bands td:first-child {{ text-align: left; color: {MUTED}; }}
    table.bands tr:last-child td {{ border-bottom: none; font-weight: 600; }}

    /* st.map has no legend of its own */
    .map-legend {{ display: flex; gap: 1.4rem; flex-wrap: wrap; margin-top: 0.6rem;
                   font-size: 0.78rem; color: {MUTED}; }}
    .map-legend span {{ display: inline-flex; align-items: center; gap: 0.4rem; }}
    .map-legend i {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
    @media (max-width: 760px) {{ .mini {{ margin-left: 0; gap: 1.5rem; }} .mini > div {{ text-align: left; }} }}
    .bar {{ height: 4px; border-radius: 2px; background: {BAR_TRACK}; margin-top: 0.7rem; overflow: hidden; }}
    .bar > span {{ display: block; height: 100%; border-radius: 2px; }}
    .accent-total {{ border-left: 3px solid {CONTROL_COLOR}; }}
    .accent-revenue {{ border-left: 3px solid {REVENUE_COLOR}; }}
    .accent-rate {{ border-left: 3px solid {CONTROL_COLOR}; }}
    .accent-roots {{ border-left: 3px solid {ROOTS_COLOR}; }}
    .accent-founders {{ border-left: 3px solid {FOUNDERS_COLOR}; }}
    .accent-world {{ border-left: 3px solid {CONTROL_COLOR}; }}
    .accent-distance {{ border-left: 3px solid {CONTROL_COLOR}; }}
    .accent-merch {{ border-left: 3px solid {REVENUE_COLOR}; }}

    .subhead {{ font-size: 0.95rem; font-weight: 600; color: {TOTAL_COLOR}; }}
    .hint {{ color: {MUTED}; font-weight: 400; font-size: 0.8rem; }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px; }}
    [data-testid="stSidebar"] .block-container {{ padding-top: 1.5rem; }}
    [data-testid="stHeaderActionElements"] {{ display: none; }}
    footer, #MainMenu {{ visibility: hidden; }}
</style>
"""
