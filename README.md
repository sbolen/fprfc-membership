# FPRFC Membership Dashboard

Streamlit dashboard for the 2026 membership export in `data/2026-memberships.csv`.
The club crest in `assets/logo.png` is shown in the header and used as the favicon.

## Brand palette

| Role | Colour |
|---|---|
| Page background | `#faf1e0` |
| Revenue (cards, lines, bars) | `#008758` |
| Roots of the Club | `#9b2246` |
| Founders Ring | `#db582e` |
| Toggles, buttons, map gradient, aggregate metrics | `#02463a` |

Revenue charts stay in the revenue green; the tier split within them uses a lighter tint of
the same hue (`#8cc9b4`). Neutral membership charts use `#02463a` with `#7ba394` for the
"other" group. The palette lives in the constants block at the top of `app.py` and in
`.streamlit/config.toml`.

## Views

- **Top-line numbers** — total memberships, total revenue, average new members per day,
  Roots of the Club, Founders Ring, countries represented, and a full-width block showing
  average distance from the reference address.
- **Growth over time** — a Memberships / Revenue metric toggle, each with a Cumulative or
  New-per-week view, broken out by tier. Revenue uses the tier prices below.
- **Geography** — members by US state (bar or choropleth map), a Members / Revenue toggle
  for the state breakdown, and members by country.

Sidebar filters: date range, membership tier, and whether to include canceled orders
(excluded by default). Filtered data can be downloaded from the bottom of the page.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Then open http://localhost:8501.

## Pricing

| Tier | Price | Active units | Active revenue |
|---|---|---|---|
| Roots of the Club | $25 | 393 | $9,825 |
| Founders Ring | $314 | 64 | $20,096 |
| **Total** | | **457** | **$29,921** |

Prices live in `TIER_PRICES` in `app.py`. Revenue is `quantity × tier price`, summed over
the current filters.

Average new members per day is the filtered membership count divided by the number of days
from the first to the last order in the selection (355 days for the full dataset → 1.3/day).

## Average distance

Straight-line (great-circle) distance from the **Gateway Arch**, St. Louis (38.6245, −90.1857).
Street addresses were removed from the export, so each member's location is approximated by:

- **US** — postcode centroid, ZIP+4 trimmed to 5 digits, from GeoNames via `pgeocode`
- **International** — city centroid, from OpenStreetMap Nominatim

Averages are weighted by quantity. The lookup is `data/geo_lookup.csv` (152 locations,
100% coverage). After adding an export with new postcodes or cities, rebuild it:

```bash
.venv/bin/pip install pgeocode requests
.venv/bin/python build_geo_lookup.py
```

Only locations not already in the lookup are queried, so re-running is cheap. Anything
that can't be geocoded is excluded from the average and the card reports the coverage.

Current figures: **206 mi** overall (7 international members average ~5,500 mi), **123 mi**
for US members only, median **16 mi**, furthest **8,854 mi** (Ho Chi Minh City).

## Notes on the data

- 456 order records, 458 memberships: `Item #` is the quantity purchased, and two orders
  (both Roots of the Club) have quantity 2. All counts on the dashboard sum quantity.
- 1 canceled order (quantity 1), excluded by default: 457 active memberships
  (393 Roots + 64 Founders).
- Repeat purchases count separately (one member has three orders). The export is
  de-identified — first name, last name, street address, email and customer note are
  removed, so repeat buyers can no longer be identified across rows. City, state and
  postcode are retained.
- `Country Code` mixes ISO codes and full names (`US` / `United States`); both normalize
  to United States. State/province values are trimmed and uppercased, and only US
  two-letter codes are used in the state view.
- Order dates arrive in two formats (`M/D/YYYY H:MM` and `YYYY-MM-DD H:MM`); both are parsed.
