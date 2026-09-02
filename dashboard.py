"""
dashboard.py
============
ESFRI KPI Dashboard — NiceGUI entry point.

URL query params are kept in sync with the dashboard state so that
any filter combination is bookmarkable and shareable.

Supported params:
  ?countries=France,Germany   comma-separated country names
  ?objective=Finance          thematic objective (or 'All')
  ?from=2020&to=2024          year range (inclusive)
  ?agg=median                 aggregation mode (sum | median)

Run:
    python dashboard.py
"""

from __future__ import annotations

import pandas as pd
from nicegui import ui
from starlette.requests import Request

from sp_analysis import (
    load_data,
    dynamic_db_prepare_by_kpi_all_countries,
    filter_data,
    aggregate_time_series,
    KPI_IDS,
    OBJECTIVES,
    get_entry,
    DashboardState,
    compute_dashboard_data,
    build_sparkline,
)

# ── Bootstrap data (shared, loaded once) ───────────────────────────────────────
raw = load_data()
long_df: pd.DataFrame = dynamic_db_prepare_by_kpi_all_countries(raw, KPI_IDS)

ALL_COUNTRIES: list[str] = sorted(long_df["countryname"].dropna().unique().tolist())
ALL_YEARS: list[int] = sorted(long_df["year"].dropna().unique().tolist())
YEAR_MIN, YEAR_MAX = min(ALL_YEARS), max(ALL_YEARS)


def apply_cessda_theme() -> None:
    ui.colors(
        primary="#1083d1",  # Blue    - hue 204
        secondary="#aa2268",  # Magenta - hue 329
        accent="#176361",  # Green   - hue 178
        positive="#1f8481",  # Green (light variant)
        info="#2cb9ed",  # Sky Blue - hue 196
        warning="#f96b06",  # Orange   - hue 25
        negative="#881b53",  # Magenta
        dark="#052438",  # Blue
    )
    ui.add_head_html("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
      body {
        font-family: 'Inter', Tahoma, sans-serif;
        font-size: 16px;
        line-height: 1.35;
        text-align: left;
      }
    </style>
    """)


# ── URL ↔ State helpers ────────────────────────────────────────────────────────
def _state_from_request(request: Request) -> DashboardState:
    """Parse query params into a fresh per-request DashboardState."""
    p = request.query_params

    raw_countries = p.get("countries", "")
    countries = (
        [c for c in raw_countries.split(",") if c in ALL_COUNTRIES]
        if raw_countries
        else []
    )

    objective = p.get("objective", "All")
    if objective not in (["All"] + OBJECTIVES):
        objective = "All"

    try:
        year_from = max(YEAR_MIN, min(YEAR_MAX, int(p.get("from", YEAR_MIN))))
    except ValueError:
        year_from = YEAR_MIN
    try:
        year_to = max(YEAR_MIN, min(YEAR_MAX, int(p.get("to", YEAR_MAX))))
    except ValueError:
        year_to = YEAR_MAX
    if year_from > year_to:
        year_from, year_to = YEAR_MIN, YEAR_MAX

    agg = p.get("agg", "sum")
    if agg not in ("sum", "median"):
        agg = "sum"

    return DashboardState(
        selected_countries=countries,
        selected_objective=objective,
        year_range=(year_from, year_to),
        agg_mode=agg,
    )


def _build_query_string(state: DashboardState) -> str:
    """Serialise state to a query string (without leading '?')."""
    parts: list[str] = []
    if state.selected_countries:
        parts.append("countries=" + ",".join(state.selected_countries))
    if state.selected_objective != "All":
        parts.append(f"objective={state.selected_objective}")
    if state.year_range != (YEAR_MIN, YEAR_MAX):
        parts.append(f"from={state.year_range[0]}&to={state.year_range[1]}")
    if state.agg_mode != "sum":
        parts.append(f"agg={state.agg_mode}")
    return "&".join(parts)


def _push_url(state: DashboardState) -> None:
    """Silently update the browser URL bar without a page reload."""
    qs = _build_query_string(state)
    url = f"/?{qs}" if qs else "/"
    ui.run_javascript(f'history.replaceState(null, "", {url!r})')


# ── Misc helpers ───────────────────────────────────────────────────────────────
def _fmt_number(v: float | None) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.0f}"


def _recompute(state: DashboardState) -> dict:
    return compute_dashboard_data(
        long_df,
        countries=state.countries_filter,
        kpis=state.active_kpis,
        year_range=state.year_range,
        agg_mode=state.agg_mode,
        reference_year=state.reference_year,
    )


# ── Page ───────────────────────────────────────────────────────────────────────
@ui.page("/")
def main_page(request: Request) -> None:
    # State is per-request (per browser tab), seeded from URL params
    state = _state_from_request(request)

    apply_cessda_theme()

    result = _recompute(state)

    # ── Layout ─────────────────────────────────────────────────────────────
    with ui.row().classes("w-full gap-0"):

        # ── Sidebar ────────────────────────────────────────────────────────
        with (
            ui.column()
            .classes("bg-white w-100 p-5 gap-4 flex-shrink-0")
            .style("min-height: 100vh; border-right: 1px solid #e0e0e0")
        ):
            ui.image("./assets/logo_2022_digital.png")
            ui.label("Annual Dashboard").classes("text-grey")

            ui.separator()

            # ── Objective filter ───────────────────────────────────────────
            with ui.column().classes("gap-2"):
                ui.label("Objective")

                objective_buttons: dict[str, ui.chip] = {}

                def _sync_objective_chips():
                    for o, chip in objective_buttons.items():
                        active = o == state.selected_objective
                        chip.props(
                            f'color={"primary" if active else "grey-3"} text-color={"white" if active else "grey-9"}'
                        )

                def make_objective_handler(obj: str):
                    def handler():
                        state.set_objective(obj)
                        _sync_objective_chips()
                        _push_url(state)
                        refresh_table()

                    return handler

                for obj in ["All"] + OBJECTIVES:
                    is_active = obj == state.selected_objective
                    chip = (
                        ui.chip(
                            obj,
                            color="primary" if is_active else "grey-3",
                            text_color="white" if is_active else "grey-9",
                        )
                        .props("clickable dense")
                        .on("click", make_objective_handler(obj))
                    )
                    objective_buttons[obj] = chip

            ui.separator()

            # ── Country selector ───────────────────────────────────────────
            with ui.column().classes("gap-2"):
                ui.label("Country").classes(" mr-32")
                country_select = (
                    ui.select(
                        options=ALL_COUNTRIES,
                        multiple=False,
                        label="Default to all",
                        value=list(state.selected_countries),
                    )
                    .classes("w-full text-lg")
                    .props("outlined dense use-chips color=primary")
                )

                def on_country_change():
                    val = country_select.value
                    state.set_countries([val] if val else [])
                    _push_url(state)
                    refresh_table()

                country_select.on("update:model-value", on_country_change)

            ui.separator()

            # ── Year range ─────────────────────────────────────────────────
            with ui.column().classes("gap-2"):
                ui.label("Year range").classes("")
                with ui.row().classes("w-full gap-2 items-center"):
                    year_start = (
                        ui.number(
                            label="From",
                            value=state.year_range[0],
                            min=YEAR_MIN,
                            max=YEAR_MAX,
                            step=1,
                        )
                        .classes("w-24")
                        .props("outlined dense color=primary")
                    )
                    ui.label("–")
                    year_end = (
                        ui.number(
                            label="To",
                            value=state.year_range[1],
                            min=YEAR_MIN,
                            max=YEAR_MAX,
                            step=1,
                        )
                        .classes("w-24")
                        .props("outlined dense color=primary")
                    )

                def on_year_change(_e=None):
                    try:
                        s = int(year_start.value)
                        e = int(year_end.value)
                        if s <= e:
                            state.set_year_range(s, e)
                            _push_url(state)
                            refresh_table()
                    except (TypeError, ValueError):
                        pass

                year_start.on("update:model-value", on_year_change)
                year_end.on("update:model-value", on_year_change)

            ui.separator()

            # ── Reset ──────────────────────────────────────────────────────
            def on_reset():
                state.reset()
                country_select.set_value(None)
                year_start.set_value(YEAR_MIN)
                year_end.set_value(YEAR_MAX)
                # agg_toggle.set_value("sum")
                _sync_objective_chips()
                _push_url(state)
                refresh_table()

            ui.button("Reset filters", on_click=on_reset).props(
                "flat dense color=secondary"
            )

        # ── Main content ───────────────────────────────────────────────────
        with ui.column().classes("flex-1 p-6 gap-4"):
            ui.markdown("""
                ### CESSDA Key Performance Indicators (C-KPIs)
                CESSDA has been a Landmark of the European Strategy Forum on Research
                Infrastructures (ESFRI) since 2016.
                CESSDA monitors its contribution to the European Research Area and alignment with the ESFRI objectives through a set of CESSDA key performance indicators (C-KPIs).
                This dashboard presents these indicators and provides an overview of the collective outcomes achieved across the consortium. It is intended to support performance monitoring and trend analysis.

                **Update frequency**: Annual
                """)

            with ui.row().classes("items-center gap-4 mb-2"):
                reference_year_label = ui.label("")

            table_container = ui.column().classes("w-full gap-0")

            def build_table_header():
                with ui.row().classes("w-full px-4 py-2 rounded-t gap-0"):
                    ui.label("KPI").classes(" flex-1 text-bold")
                    ui.label("Sum").classes(" w-28 text-right text-bold")
                    ui.label("Median").classes("w-28 text-right text-bold")
                    ui.label("Countries").classes(" w-20 text-right text-bold")
                    ui.label("Trend").classes(" w-32 text-right text-bold")

            def refresh_table():
                nonlocal result
                table_container.clear()
                result = _recompute(state)
                stats_df: pd.DataFrame = result["stats"]
                ts_df: pd.DataFrame = result["time_series"]

                ref_year = (
                    state.reference_year
                    if state.reference_year
                    else (int(stats_df["year"].iloc[0]) if not stats_df.empty else "—")
                )
                reference_year_label.set_text(f"Stats for year: {ref_year}")

                with table_container:
                    build_table_header()

                    kpis_to_show = state.active_kpis
                    stats_index = (
                        stats_df.set_index("kpi")
                        if not stats_df.empty
                        else pd.DataFrame(
                            columns=["kpi", "sum", "median", "n_countries"]
                        ).set_index("kpi")
                    )

                    for kpi_id in kpis_to_show:
                        entry = get_entry(kpi_id)
                        label_text = entry.label if entry else kpi_id
                        unit_text = entry.unit if entry else ""
                        row_stats = (
                            stats_index.loc[kpi_id]
                            if kpi_id in stats_index.index
                            else None
                        )
                        sum_val = row_stats["sum"] if row_stats is not None else None
                        median_val = (
                            row_stats["median"] if row_stats is not None else None
                        )
                        n_val = (
                            row_stats["n_countries"] if row_stats is not None else None
                        )

                        with ui.row().classes(
                            "w-full px-4 py-3 border-b items-center gap-0"
                        ):
                            with ui.column().classes("flex-1 gap-0"):
                                ui.label(label_text)
                                if entry and entry.description:
                                    ui.label(unit_text).classes("text-xs")
                            ui.label(_fmt_number(sum_val)).classes("w-28 text-right")
                            ui.label(_fmt_number(median_val)).classes("w-28 text-right")
                            ui.label(_fmt_number(n_val)).classes("w-20 text-right")
                            with ui.element("div").classes("w-32 flex justify-end"):
                                kpi_ts = ts_df[ts_df["kpi"] == kpi_id]
                                if not kpi_ts.dropna(subset=["value"]).empty:
                                    all_countries_ts = aggregate_time_series(
                                        filter_data(
                                            long_df,
                                            kpis=[kpi_id],
                                            year_range=state.year_range,
                                        ),
                                        mode="median",
                                    )
                                    spark = build_sparkline(
                                        ts_df,
                                        kpi_id,
                                        width=120,
                                        height=36,
                                        baseline_ts=all_countries_ts,
                                    )
                                    ui.altair(spark).classes("w-32")
                                else:
                                    ui.label("No data").classes("text-xs")

            # Initial render
            with table_container:
                build_table_header()

            reference_year_label.set_text(
                f"Stats for year: {int(result['stats']['year'].iloc[0]) if not result['stats'].empty else '—'}"
            )
            refresh_table()

    with ui.footer():
        ui.markdown(
            """**Data Disclaimer**: The data displayed in this dashboard is collected from CESSDA Service Providers.
            While KPI definitions have been standardised where possible, differences in organisational context,
            reporting practices, and data quality may affect comparability. Figures may be updated as source data is revised."""
        )


ui.run(title="CESSDA Public Dashboard", port=8888, reload=True)
