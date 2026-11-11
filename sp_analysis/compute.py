"""
kpi_engine/compute.py
=====================
Layer 2 — Aggregation Engine.

Operates exclusively on the output of `prepare_by_kpi_all_countries`.
🔒 NEVER modifies or monkey-patches Layer 1 (data.py).

Canonical input format: countryname | year | kpi | value
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .registry import AggMode


# ── Public API ─────────────────────────────────────────────────────────────────

def filter_data(
    long_df: pd.DataFrame,
    countries: list[str] | None = None,
    kpis: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """Subset a long-format dataframe produced by `prepare_by_kpi_all_countries`.

    All filters are optional.  Passing None for a filter means "keep all".

    Parameters
    ----------
    long_df:
        Output of ``prepare_by_kpi_all_countries`` —
        columns: countryname, year, kpi, value.
    countries:
        List of country names to keep.  None → keep all.
    kpis:
        List of KPI ids to keep.  None → keep all.
    year_range:
        Inclusive (start, end) year tuple.  None → keep all years.
    """
    df = long_df.copy()
    if countries:
        df = df[df['countryname'].isin(countries)]
    if kpis:
        df = df[df['kpi'].isin(kpis)]
    if year_range:
        df = df[df['year'].between(*year_range)]
    return df


def aggregate_time_series(
    long_df: pd.DataFrame,
    mode: AggMode = 'sum',
) -> pd.DataFrame:
    """Aggregate across countries per (kpi, year).

    Parameters
    ----------
    long_df:
        Already-filtered long-format dataframe (countryname, year, kpi, value).
    mode:
        ``'sum'``    — sum values across selected countries.
        ``'median'`` — median across countries (ignores NaN).

    Returns
    -------
    DataFrame with columns: year, kpi, value
    """
    long_df = long_df[long_df['value'] != 0]  # zero means "not reported"
    grouped = long_df.groupby(['kpi', 'year'])['value']
    if mode == 'sum':
        result = grouped.sum(min_count=1)
    elif mode == 'median':
        result = grouped.median()
    else:
        raise ValueError(f"Unknown aggregation mode: {mode!r}. Use 'sum' or 'median'.")
    return result.reset_index()


def latest_stats(
    long_df: pd.DataFrame,
    reference_year: int | None = None,
) -> pd.DataFrame:
    """Compute per-KPI summary statistics for the most recent available year.

    Parameters
    ----------
    long_df:
        Long-format dataframe (countryname, year, kpi, value).
    reference_year:
        If provided, use this year; otherwise use the latest year with data.

    Returns
    -------
    DataFrame with columns: kpi, year, sum, median, n_countries
    """
    df = long_df.dropna(subset=['value'])
    if df.empty:
        return pd.DataFrame(columns=['kpi', 'year', 'sum', 'median', 'n_countries'])

    if reference_year is None:
        reference_year = int(df['year'].max())

    df = df[df['value'] != 0]  # zero means "not reported"
    snapshot = df[df['year'] == reference_year]
    stats = (
        snapshot.groupby('kpi')['value']
        .agg(
            sum='sum',
            median='median',
            n_countries='count',
        )
        .reset_index()
    )
    stats['year'] = reference_year
    return stats


def compute_dashboard_data(
    long_df: pd.DataFrame,
    countries: list[str] | None = None,
    kpis: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    agg_mode: AggMode = 'sum',
    reference_year: int | None = None,
) -> dict:
    """Single entry-point for the NiceGUI dashboard.

    Combines filtering, time-series aggregation, and latest-year stats
    into one call.  Returns a dict so callers can access only what they need.

    Parameters
    ----------
    long_df:
        Output of ``prepare_by_kpi_all_countries``.
    countries:
        Countries to include.  None → all.
    kpis:
        KPIs to include.  None → all.
    year_range:
        Year window.  None → all years.
    agg_mode:
        Aggregation mode for the time series ('sum' or 'median').
    reference_year:
        Year used for the stats table.  None → latest with data.

    Returns
    -------
    dict with keys:
        ``filtered``   — filtered long dataframe (one row per country/year/kpi)
        ``time_series`` — aggregated time series (year, kpi, value)
        ``stats``       — latest-year stats (kpi, year, sum, median, n_countries)
    """
    filtered = filter_data(long_df, countries=countries, kpis=kpis, year_range=year_range)
    time_series = aggregate_time_series(filtered, mode=agg_mode)
    stats = latest_stats(filtered, reference_year=reference_year)
    return {
        'filtered': filtered,
        'time_series': time_series,
        'stats': stats,
    }
