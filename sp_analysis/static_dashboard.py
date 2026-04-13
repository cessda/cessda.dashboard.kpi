import pandas as pd
import altair as alt


# ── KPI metadata ───────────────────────────────────────────────────────────────

KPI_LABELS = {
    'c1_visits':         'C-KPI-01 Web visits',
    'c2_user':           'C-KPI-02 User accounts',

    'c3_pdoDeliver_pid': 'C-KPI-03 PDO delivered (PID)',

    'c4_events':         'C-KPI-04 Edu. events',
    'c6_eAttendees':     'C-KPI-06 Edu. attendees',
    'c8_allEvent':       'C-KPI-08 All events',
    'c10_pdoStored_pid': 'C-KPI-10 PDO stored (PID)',
    'c13_staff':         'C-KPI-13 National staff',
    'c14_nfunds':        'C-KPI-14 National funding',
    'c15_cstaff':        'C-KPI-15 CESSDA staff',
    'c16_cfunds':        'C-KPI-16 CESSDA activities',
    'c19_pub':           'C-KPI-19 Publications',
}

STATUS_DOMAIN = ['Validated', 'To be validated', 'Missing']
STATUS_RANGE  = ['steelblue', 'grey', 'red']


# ── Data helpers ───────────────────────────────────────────────────────────────

def load_data(source: str = 'data/sp_data.csv') -> pd.DataFrame:
    return pd.read_csv(source)


def clean_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Coerce a column to numeric, converting invalid values to NaN."""
    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def prepare_by_kpi_all_countries(df: pd.DataFrame, kpis: list[str]) -> pd.DataFrame:
    """Aggregate per country + year, melt into long format grouped by KPI.

    Returns columns: year, countryname, kpi, value
    """
    frames = []
    for col in kpis:
        tmp = clean_column(df, col)
        agg = tmp.groupby(['countryname', 'year'])[col].sum(min_count=1).reset_index()
        agg = agg.rename(columns={col: 'value'})
        agg['kpi'] = KPI_LABELS.get(col, col)
        frames.append(agg)
    return pd.concat(frames, ignore_index=True)


# ── Chart helper ───────────────────────────────────────────────────────────────

def facet_chart_by_country(
    data: pd.DataFrame,
    country: str,
    title: str,
    columns: int = 4,
) -> alt.FacetChart:
    country_data = data[data['countryname'] == country].copy()
    country_data['status'] = country_data.apply(
        lambda r: 'To be validated' if r['year'] == 2026
        else ('Validated' if pd.notna(r['value']) else 'Missing'),
        axis=1,
    )

    base = alt.Chart(country_data)
    xy = dict(
        x=alt.X('year:O', title=None),
        y=alt.Y('value:Q', title=None, axis=alt.Axis(tickCount=3, grid=False)),
    )
    color = alt.Color(
        'status:N',
        scale=alt.Scale(domain=STATUS_DOMAIN, range=STATUS_RANGE),
    )

    line = base.mark_line(color='steelblue').encode(**xy)

    dots = (
        base.transform_filter('isValid(datum.value)')
        .mark_point(filled=True)
        .encode(
            **xy,
            color=color,
            size=alt.condition(
                alt.datum.year == 2026,
                alt.value(120),
                alt.value(50),
            ),
        )
    )

    nan_markers = (
        base.transform_filter('!isValid(datum.value)')
        .mark_point(filled=True, size=60, opacity=0.6, strokeWidth=2)
        .encode(
            x='year:O',
            y=alt.value(0),
            color=color,
        )
    )

    return (
        (line + dots + nan_markers)
        .properties(width=300)
        .facet(
            facet=alt.Facet(
                'kpi:N',
                header=alt.Header(titleOrient='top', labelOrient='top'),
                title=None,
            ),
            columns=columns,
        )
        .configure_header(titleFontSize=20)
        .resolve_scale(y='independent')
        .resolve_axis(x='independent')
        .properties(
            title=alt.TitleParams(
                text=title, fontSize=16, fontWeight='bold', anchor='middle',
            )
        )
        .configure_view(stroke=None)
        .configure_legend(orient='top', direction='horizontal', title=None)
    )
