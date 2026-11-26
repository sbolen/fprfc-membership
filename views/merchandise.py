"""Merchandise store page — Printful order export.

Run the whole dashboard with `streamlit run app.py`; this page appears in the sidebar
navigation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import (
    BG, CONTROL_COLOR, GRID, MUTED, REVENUE_COLOR, STYLE, TOTAL_COLOR,
    chart_layout, fdate, header_html, human, logo_data_uri, money, pct, stamp,
)

BASE = Path(__file__).parent.parent
DATA_PATH = BASE / "data" / "printful-orders.csv"
LOGO_PATH = BASE / "assets" / "logo.png"

STATUS_COLORS = {
    "Fulfilled": REVENUE_COLOR,
    "Being Fulfilled": "#7fb9a0",
    "Waiting for Fulfillment": "#02786a",
    "Canceled": MUTED,
}

# Short labels so the chart axis does not clip at narrow widths.
STATUS_SHORT = {
    "Fulfilled": "Fulfilled",
    "Being Fulfilled": "In progress",
    "Waiting for Fulfillment": "Waiting",
    "Canceled": "Canceled",
}


@st.cache_data(show_spinner=False)
def load_orders(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ("Store", "Order", "Status", "City", "State Code", "Postcode", "Country Code"):
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["Amount"] = pd.to_numeric(
        df["Total"].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce"
    ).fillna(0.0)
    df["Order Date"] = pd.to_datetime(df["Date"], format="%B %d, %Y", errors="coerce")
    df = df.dropna(subset=["Order Date"])

    df["Canceled"] = df["Status"].str.lower().eq("canceled")
    df["State"] = df["State Code"].str.upper()
    return df.sort_values("Order Date").reset_index(drop=True)



data_mtime = DATA_PATH.stat().st_mtime
df_all = load_orders(str(DATA_PATH), data_mtime)

# ------------------------------- sidebar ----------------------------------- #
with st.sidebar:
    st.markdown('<div class="eyebrow">Filters</div>', unsafe_allow_html=True)

    include_canceled = st.toggle("Include canceled orders", value=False)
    store_options = sorted(df_all["Store"].unique())
    stores = st.multiselect("Store", store_options, default=store_options)

    min_date = df_all["Order Date"].min().date()
    max_date = df_all["Order Date"].max().date()
    date_range = st.slider("Order date", min_value=min_date, max_value=max_date,
                           value=(min_date, max_date), format="MMM D, YYYY")

df = df_all[df_all["Store"].isin(stores)]
df = df[(df["Order Date"].dt.date >= date_range[0]) & (df["Order Date"].dt.date <= date_range[1])]
if not include_canceled:
    df = df[~df["Canceled"]]
df = df.copy()

if df.empty:
    st.title("Merchandise")
    st.info("No orders match the current filters.")
    st.stop()

# ------------------------------- header ------------------------------------ #
logo_uri = logo_data_uri(str(LOGO_PATH), LOGO_PATH.stat().st_mtime)
st.markdown(
    header_html(
        logo_uri,
        eyebrow="FPRFC · Merchandise",
        title="Merch Store",
        stamp_value=stamp(data_mtime),
        stamp_sub=f"data through {fdate(df_all['Order Date'].max())}",
    ),
    unsafe_allow_html=True,
)

n_orders = len(df)
gross = float(df["Amount"].sum())
aov = gross / n_orders if n_orders else 0.0
fulfilled = int((df["Status"] == "Fulfilled").sum())
in_progress = int(df["Status"].isin(["Waiting for Fulfillment", "Being Fulfilled"]).sum())
n_states = df["State"].nunique()

st.markdown(
    f'<div class="subtitle">{human(n_orders)} orders · '
    f'{fdate(df["Order Date"].min())} – {fdate(df["Order Date"].max())}</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="cards">
      <div class="card accent-merch">
        <div class="label">Orders</div>
        <div class="value">{human(n_orders)}</div>
        <div class="note">{len(stores)} store{"" if len(stores) == 1 else "s"}</div>
      </div>
      <div class="card accent-revenue">
        <div class="label">Gross sales</div>
        <div class="value">{money(gross)}</div>
        <div class="note">sum of order totals</div>
      </div>
      <div class="card accent-merch">
        <div class="label">Avg order value</div>
        <div class="value">{money(aov)}</div>
        <div class="note">gross sales ÷ orders</div>
      </div>
      <div class="card accent-revenue">
        <div class="label">Fulfilled</div>
        <div class="value">{human(fulfilled)}</div>
        <div class="note">{pct(fulfilled, n_orders)} of orders</div>
        <div class="bar"><span style="width:{100 * fulfilled / n_orders:.1f}%; background:{REVENUE_COLOR};"></span></div>
      </div>
      <div class="card accent-total">
        <div class="label">In progress</div>
        <div class="value">{human(in_progress)}</div>
        <div class="note">waiting or being fulfilled</div>
      </div>
      <div class="card accent-total">
        <div class="label">States shipped to</div>
        <div class="value">{n_states}</div>
        <div class="note">from {human(df['City'].nunique())} cities</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------- sales over time -------------------------------- #
st.write("")
st.markdown('<div class="section-title">Merchandise sales over time</div>', unsafe_allow_html=True)

sub_slot = st.empty()
mode = st.segmented_control(
    "Sales view", ["Monthly", "Cumulative"], default="Monthly",
    label_visibility="collapsed",
) or "Monthly"

sub_slot.markdown(
    f'<div class="section-sub">'
    f'{"Revenue per month" if mode == "Monthly" else "Cumulative revenue"} · '
    f'{fdate(df["Order Date"].min())} to {fdate(df["Order Date"].max())}</div>',
    unsafe_allow_html=True,
)

monthly = df.groupby(df["Order Date"].dt.to_period("M"))["Amount"].sum()
monthly.index = monthly.index.to_timestamp()

fig = go.Figure()
if mode == "Monthly":
    fig.add_trace(go.Bar(
        x=monthly.index, y=monthly.values, marker=dict(color=REVENUE_COLOR, line=dict(width=0)),
        hovertemplate="%{x|%b %Y}<br>$%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(bargap=0.35)
else:
    fig.add_trace(go.Scatter(
        x=monthly.index, y=monthly.cumsum(), mode="lines",
        line=dict(color=REVENUE_COLOR, width=2.6), fill="tozeroy",
        fillcolor="rgba(0,135,88,0.10)",
        hovertemplate="%{x|%b %Y}<br>$%{y:,.2f}<extra></extra>",
    ))
    fig.update_yaxes(rangemode="tozero")

fig.update_layout(showlegend=False)
fig.update_yaxes(tickprefix="$", tickformat=",.0f")
st.plotly_chart(chart_layout(fig, height=330), width="stretch", config={"displayModeBar": False})

# ------------------------- status + geography ------------------------------ #
st.write("")
c1, c2 = st.columns([1, 1.4], gap="large")

with c1:
    st.markdown('<div class="subhead">Order status</div>', unsafe_allow_html=True)
    by_status = df["Status"].value_counts().sort_values()
    sfig = go.Figure(go.Bar(
        y=[STATUS_SHORT.get(s, s) for s in by_status.index], x=by_status.values, orientation="h",
        marker=dict(color=[STATUS_COLORS.get(s, CONTROL_COLOR) for s in by_status.index],
                    line=dict(width=0)),
        text=by_status.values, textposition="outside", cliponaxis=False,
        customdata=by_status.index,
        hovertemplate="%{customdata}: %{x} orders<extra></extra>",
    ))
    sfig.update_xaxes(showgrid=True, gridcolor=GRID, showticklabels=False, ticks="",
                      range=[0, max(by_status.max() * 1.18, 2)])
    sfig.update_yaxes(showgrid=False, ticks="")
    sfig.update_layout(showlegend=False)
    st.plotly_chart(chart_layout(sfig, height=260), width="stretch",
                    config={"displayModeBar": False})

with c2:
    st.markdown('<div class="subhead">Where orders ship</div>', unsafe_allow_html=True)
    by_state = df.groupby("State")["Amount"].agg(["size", "sum"]).sort_values("size", ascending=False)
    top = by_state.head(8).sort_values("size")
    gfig = go.Figure(go.Bar(
        y=top.index, x=top["size"], orientation="h",
        marker=dict(color=CONTROL_COLOR, line=dict(width=0)),
        text=[f"{int(n)} · {money(v)}" for n, v in zip(top["size"], top["sum"])],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x} orders<extra></extra>",
    ))
    gfig.update_xaxes(showgrid=True, gridcolor=GRID, showticklabels=False, ticks="",
                      range=[0, top["size"].max() * 1.45])
    gfig.update_yaxes(showgrid=False, ticks="")
    gfig.update_layout(showlegend=False)
    st.plotly_chart(chart_layout(gfig, height=260), width="stretch",
                    config={"displayModeBar": False})
    st.caption(
        f"{human(int(by_state['size'].sum()))} orders across {len(by_state)} states · "
        f"{pct(by_state['size'].iloc[0], by_state['size'].sum())} in {by_state.index[0]}"
    )

# ------------------------------ recent orders ------------------------------ #
st.write("")
st.markdown('<div class="section-title">Recent orders</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">Names and street addresses are not included in this export</div>',
    unsafe_allow_html=True,
)

recent = df.sort_values("Order Date", ascending=False).head(12).copy()
recent["Date"] = recent["Order Date"].dt.strftime("%b %-d, %Y")
recent["Location"] = recent["City"].str.title() + ", " + recent["State"]
recent = recent[["Order", "Date", "Status", "Amount", "Location"]].rename(columns={"Amount": "Total"})

st.dataframe(
    recent,
    hide_index=True,
    width="stretch",
    column_config={"Total": st.column_config.NumberColumn(format="$%.2f")},
)

# -------------------------------- footer ----------------------------------- #
st.write("")
with st.expander("About this data"):
    st.markdown(
        f"""
Source: `data/printful-orders.csv` · {len(df_all):,} orders · {money(float(df_all["Amount"].sum()))} gross.

- Printful order export, de-identified: recipient name and street address are removed;
  city, state and postcode are retained. The dashboard never displays a buyer's identity.
- Two stores appear in the export — Forest Park Rangers FC and Personal orders — and both
  are included by default; use the sidebar to isolate either.
- Canceled orders are excluded by default ({int(df_all["Canceled"].sum())} in the file) and
  contribute $0.00 to gross sales.
- Totals are the order totals from Printful; they are not net of Printful's fulfilment or
  shipping costs, so this is revenue, not margin.
        """
    )
