"""
tests/test_layer2.py
====================
Tests for the new additive Layer 2 modules:
  - registry.py
  - compute.py
  - charts.py
  - ui_state.py

Run with:  pytest tests/test_layer2.py -v
"""

import pytest
import numpy as np
import pandas as pd


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def long_df() -> pd.DataFrame:
    """Synthetic long-format dataframe (output of prepare_by_kpi_all_countries)."""
    rows = []
    for country in ['Alpha', 'Beta', 'Gamma']:
        for year in [2021, 2022, 2023]:
            for kpi in ['c1_visits', 'c2_user', 'c13_staff']:
                val = float(hash((country, year, kpi)) % 500 + 10)
                rows.append({'countryname': country, 'year': year, 'kpi': kpi, 'value': val})
    # Inject a NaN
    rows.append({'countryname': 'Delta', 'year': 2022, 'kpi': 'c1_visits', 'value': np.nan})
    return pd.DataFrame(rows)


# ── Registry ───────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_all_kpi_ids_in_kpi_labels(self):
        from sp_analysis.registry import KPI_REGISTRY
        from sp_analysis.static_dashboard import KPI_LABELS
        for kpi_id in KPI_REGISTRY:
            assert kpi_id in KPI_LABELS, \
                f'Registry id {kpi_id!r} not found in KPI_LABELS — id mismatch!'

    def test_objectives_non_empty(self):
        from sp_analysis.registry import OBJECTIVES
        assert len(OBJECTIVES) > 0

    def test_get_kpis_for_objective_all(self):
        from sp_analysis.registry import get_kpis_for_objective, KPI_IDS
        assert get_kpis_for_objective('All') == KPI_IDS
        assert get_kpis_for_objective(None) == KPI_IDS

    def test_get_kpis_for_specific_objective(self):
        from sp_analysis.registry import get_kpis_for_objective, OBJECTIVES
        obj = OBJECTIVES[0]
        kpis = get_kpis_for_objective(obj)
        assert len(kpis) > 0
        assert all(isinstance(k, str) for k in kpis)

    def test_get_entry_returns_entry(self):
        from sp_analysis.registry import get_entry
        e = get_entry('c1_visits')
        assert e is not None
        assert e.id == 'c1_visits'
        assert e.label
        assert e.objective

    def test_get_entry_unknown_returns_none(self):
        from sp_analysis.registry import get_entry
        assert get_entry('not_a_real_kpi') is None


# ── Compute ────────────────────────────────────────────────────────────────────

class TestFilterData:
    def test_filter_by_country(self, long_df):
        from sp_analysis.compute import filter_data
        result = filter_data(long_df, countries=['Alpha'])
        assert set(result['countryname'].unique()) == {'Alpha'}

    def test_filter_by_kpi(self, long_df):
        from sp_analysis.compute import filter_data
        result = filter_data(long_df, kpis=['c1_visits'])
        assert set(result['kpi'].unique()) == {'c1_visits'}

    def test_filter_by_year_range(self, long_df):
        from sp_analysis.compute import filter_data
        result = filter_data(long_df, year_range=(2022, 2022))
        assert set(result['year'].unique()) == {2022}

    def test_no_filter_returns_all(self, long_df):
        from sp_analysis.compute import filter_data
        result = filter_data(long_df)
        assert len(result) == len(long_df)

    def test_does_not_mutate_input(self, long_df):
        from sp_analysis.compute import filter_data
        original_len = len(long_df)
        filter_data(long_df, countries=['Alpha'])
        assert len(long_df) == original_len


class TestAggregateTimeSeries:
    def test_sum_returns_one_row_per_year_kpi(self, long_df):
        from sp_analysis.compute import aggregate_time_series
        result = aggregate_time_series(long_df, mode='sum')
        assert set(result.columns) >= {'year', 'kpi', 'value'}
        # No duplicate (year, kpi) pairs
        assert not result.duplicated(subset=['year', 'kpi']).any()

    def test_median_mode(self, long_df):
        from sp_analysis.compute import aggregate_time_series
        result = aggregate_time_series(long_df, mode='median')
        assert not result.empty

    def test_invalid_mode_raises(self, long_df):
        from sp_analysis.compute import aggregate_time_series
        with pytest.raises(ValueError):
            aggregate_time_series(long_df, mode='mean')

    def test_nan_ignored_in_sum(self, long_df):
        from sp_analysis.compute import filter_data, aggregate_time_series
        df = filter_data(long_df, kpis=['c1_visits'], year_range=(2022, 2022))
        result = aggregate_time_series(df, mode='sum')
        # Delta had NaN for c1_visits 2022; sum should still be finite for 2022
        val = result.loc[result['year'] == 2022, 'value']
        assert not val.isna().all()

    def test_zero_is_treated_as_missing(self):
        from sp_analysis.compute import aggregate_time_series
        df = pd.DataFrame([
            {'countryname': 'A', 'year': 2024, 'kpi': 'k', 'value': 10.0},
            {'countryname': 'B', 'year': 2024, 'kpi': 'k', 'value': 0.0},
        ])
        assert aggregate_time_series(df, mode='sum')['value'].tolist() == [10.0]
        assert aggregate_time_series(df, mode='median')['value'].tolist() == [10.0]


class TestLatestStats:
    def test_returns_required_columns(self, long_df):
        from sp_analysis.compute import latest_stats
        result = latest_stats(long_df)
        assert set(result.columns) >= {'kpi', 'year', 'sum', 'median', 'n_countries'}

    def test_respects_reference_year(self, long_df):
        from sp_analysis.compute import latest_stats
        result = latest_stats(long_df, reference_year=2021)
        assert (result['year'] == 2021).all()

    def test_zero_excluded_from_stats(self):
        from sp_analysis.compute import latest_stats
        df = pd.DataFrame([
            {'countryname': 'A', 'year': 2024, 'kpi': 'k', 'value': 10.0},
            {'countryname': 'B', 'year': 2024, 'kpi': 'k', 'value': 20.0},
            {'countryname': 'C', 'year': 2024, 'kpi': 'k', 'value': 0.0},
        ])
        row = latest_stats(df).iloc[0]
        assert row['n_countries'] == 2
        assert row['sum'] == 30
        assert row['median'] == 15

    def test_all_zero_latest_year_does_not_fall_back(self):
        from sp_analysis.compute import latest_stats
        df = pd.DataFrame([
            {'countryname': 'A', 'year': 2023, 'kpi': 'k', 'value': 10.0},
            {'countryname': 'A', 'year': 2024, 'kpi': 'k', 'value': 0.0},
        ])
        # 2024 is still the reference year, so there is no 2023 row
        assert latest_stats(df).empty

    def test_empty_df_returns_empty(self):
        from sp_analysis.compute import latest_stats
        empty = pd.DataFrame(columns=['countryname', 'year', 'kpi', 'value'])
        result = latest_stats(empty)
        assert result.empty


class TestComputeDashboardData:
    def test_returns_all_keys(self, long_df):
        from sp_analysis.compute import compute_dashboard_data
        result = compute_dashboard_data(long_df)
        assert {'filtered', 'time_series', 'stats'} == set(result.keys())

    def test_filtered_respects_countries(self, long_df):
        from sp_analysis.compute import compute_dashboard_data
        result = compute_dashboard_data(long_df, countries=['Alpha'])
        assert set(result['filtered']['countryname'].unique()) == {'Alpha'}


# ── Charts ─────────────────────────────────────────────────────────────────────

class TestChartBuilders:
    @pytest.fixture
    def time_series(self, long_df):
        from sp_analysis.compute import aggregate_time_series
        return aggregate_time_series(long_df, mode='sum')

    def test_build_sparkline_returns_chart(self, time_series):
        import altair as alt
        from sp_analysis.charts import build_sparkline
        chart = build_sparkline(time_series, kpi='c1_visits')
        assert isinstance(chart, (alt.Chart, alt.LayerChart))

    def test_build_kpi_chart_returns_chart(self, time_series):
        import altair as alt
        from sp_analysis.charts import build_kpi_chart
        chart = build_kpi_chart(time_series, kpi='c1_visits', title='Visits')
        assert chart is not None

    def test_build_comparison_chart(self, long_df):
        import altair as alt
        from sp_analysis.charts import build_comparison_chart
        chart = build_comparison_chart(long_df, kpi='c1_visits', selected_countries=['Alpha', 'Beta'])
        assert chart is not None


# ── UI State ───────────────────────────────────────────────────────────────────

class TestDashboardState:
    def test_default_objective_is_all(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        assert s.selected_objective == 'All'

    def test_active_kpis_all_when_no_objective(self):
        from sp_analysis.ui_state import DashboardState
        from sp_analysis.registry import KPI_IDS
        s = DashboardState()
        assert s.active_kpis == KPI_IDS

    def test_countries_filter_none_when_empty(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        assert s.countries_filter is None

    def test_countries_filter_list_when_set(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        s.set_countries(['Alpha', 'Beta'])
        assert s.countries_filter == ['Alpha', 'Beta']

    def test_listener_called_on_change(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        calls = []
        s.on_change(lambda: calls.append(1))
        s.set_countries(['Alpha'])
        assert len(calls) == 1

    def test_multiple_listeners(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        log = []
        s.on_change(lambda: log.append('a'))
        s.on_change(lambda: log.append('b'))
        s.set_objective('Finance')
        assert log == ['a', 'b']

    def test_reset_restores_defaults(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        s.set_countries(['Alpha'])
        s.set_objective('Finance')
        s.reset()
        assert s.selected_countries == []
        assert s.selected_objective == 'All'

    def test_invalid_agg_mode_raises(self):
        from sp_analysis.ui_state import DashboardState
        s = DashboardState()
        with pytest.raises(ValueError):
            s.set_agg_mode('mean')
