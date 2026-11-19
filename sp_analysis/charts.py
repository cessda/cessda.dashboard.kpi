"""
kpi_engine/charts.py
====================
Layer 2 — New chart builders for the NiceGUI dashboard.

🔒 `facet_chart_by_country` lives in data.py and is NOT touched here.
   All new functions operate on the output of compute.py (time-series format).

Input contract for all builders:
    DataFrame with columns: year, kpi, value
    (output of aggregate_time_series or filter_data)
"""

from __future__ import annotations

import pandas as pd
import altair as alt

from .static_dashboard import STATUS_DOMAIN, STATUS_RANGE


# ── Shared theme ───────────────────────────────────────────────────────────────

_FONT = 'IBM Plex Sans'
_COLOR_PRIMARY = '#1083d1'   # blue-600
_COLOR_MEDIAN  = '#059669'   # emerald-600


def _base_theme() -> dict:
    return dict(
        config=alt.Config(
            font=_FONT,
            view=alt.ViewConfig(stroke=None),
            axis=alt.AxisConfig(grid=False, labelColor='#6b7280', titleColor='#374151'),
            legend=alt.LegendConfig(orient='top', direction='horizontal', title=None),
        )
    )


# ── Mini sparkline (for KPI table rows) ───────────────────────────────────────
def build_sparkline(
    ts_df: pd.DataFrame,
    kpi_id: str,
    width: int = 120,
    height: int = 36,
    baseline_ts: pd.DataFrame | None = None,
) -> alt.Chart:
    kpi_ts = ts_df[ts_df['kpi'] == kpi_id][['year', 'value']]
    
    base = alt.Chart(kpi_ts).mark_line(color='#1083d1', strokeWidth=1.5).encode(
        x=alt.X('year:O', axis=None),
        y=alt.Y('value:Q', axis=None, scale=alt.Scale(zero=False)),
    )
    
    layers = [base]
    
    if baseline_ts is not None:
        bl_ts = baseline_ts[baseline_ts['kpi'] == kpi_id][['year', 'value']]
        baseline = alt.Chart(bl_ts).mark_line(
            color='#94a3b8', strokeWidth=1, strokeDash=[2, 2]
        ).encode(
            x=alt.X('year:O', axis=None),
            y=alt.Y('value:Q', axis=None, scale=alt.Scale(zero=False)),
        )
        layers.append(baseline)
    
    return (
        alt.layer(*layers)
        .properties(width=width, height=height)
        .configure_view(strokeWidth=0)
    )

# ── Full KPI line chart (for detail panel) ────────────────────────────────────

def build_kpi_chart(
    time_series: pd.DataFrame,
    kpi: str,
    title: str = '',
    width: int = 320,
    height: int = 180,
    show_sum: bool = True,
    show_median: bool = False,
) -> alt.LayerChart:
    """Full-size line chart for a single KPI, with optional sum/median overlays.

    Parameters
    ----------
    time_series:
        Aggregated series — columns: year, kpi, value.
        Pass the output of ``aggregate_time_series`` (already one row per year).
    kpi:
        KPI id to plot.
    title:
        Chart title.  Empty string → no title.
    show_sum, show_median:
        Which aggregation lines to render.  At least one must be True.
    """
    data = time_series[time_series['kpi'] == kpi].copy()

    layers = []

    if show_sum:
        sum_data = data.dropna(subset=['value'])
        layers.append(
            alt.Chart(sum_data)
            .mark_line(color=_COLOR_PRIMARY, strokeWidth=2)
            .encode(
                x=alt.X('year:O', title=None),
                y=alt.Y('value:Q', title=None, axis=alt.Axis(tickCount=4, grid=False)),
                tooltip=[alt.Tooltip('year:O'), alt.Tooltip('value:Q', format=',.0f')],
            )
        )
        layers.append(
            alt.Chart(sum_data)
            .mark_point(filled=True, size=50, color=_COLOR_PRIMARY)
            .encode(x='year:O', y='value:Q')
        )

    chart = alt.layer(*layers).properties(width=width, height=height)

    if title:
        chart = chart.properties(
            title=alt.TitleParams(text=title, fontSize=13, fontWeight='normal', color='#374151')
        )

    return chart.configure(**_base_theme()['config'].to_dict())


# ── Comparison chart (selected countries vs. global median) ───────────────────

def build_comparison_chart(
    long_df: pd.DataFrame,
    kpi: str,
    selected_countries: list[str],
    width: int = 400,
    height: int = 200,
) -> alt.LayerChart:
    """Overlay selected country lines against the cross-country median.

    Parameters
    ----------
    long_df:
        Filtered long-format dataframe (countryname, year, kpi, value).
        Typically the ``filtered`` key from ``compute_dashboard_data``.
    kpi:
        KPI id to plot.
    selected_countries:
        Countries to highlight individually.
    """
    data = long_df[long_df['kpi'] == kpi].copy()

    # Global median band
    median_df = (
        data.groupby('year')['value']
        .median()
        .reset_index()
        .rename(columns={'value': 'median'})
    )

    median_layer = (
        alt.Chart(median_df)
        .mark_line(
            color=_COLOR_MEDIAN,
            strokeWidth=1.5,
            strokeDash=[4, 3],
            opacity=0.7,
        )
        .encode(
            x=alt.X('year:O', title=None),
            y=alt.Y('median:Q', title=None, axis=alt.Axis(tickCount=4, grid=False)),
            tooltip=[
                alt.Tooltip('year:O'),
                alt.Tooltip('median:Q', title='Global median', format=',.0f'),
            ],
        )
    )

    # Selected countries
    selected_df = data[data['countryname'].isin(selected_countries)].dropna(subset=['value'])

    country_layer = (
        alt.Chart(selected_df)
        .mark_line(strokeWidth=2)
        .encode(
            x='year:O',
            y=alt.Y('value:Q', title=None),
            color=alt.Color('countryname:N', legend=alt.Legend(title='Country')),
            tooltip=[
                alt.Tooltip('countryname:N'),
                alt.Tooltip('year:O'),
                alt.Tooltip('value:Q', format=',.0f'),
            ],
        )
    )

    return (
        alt.layer(median_layer, country_layer)
        .properties(width=width, height=height)
        .configure(**_base_theme()['config'].to_dict())
    )
