import pandas as pd
import altair as alt


def load_data(source: str = 'data/sp_data.csv') -> pd.DataFrame:
    df = pd.read_csv(source)
    return df


def clean_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Coerce column to numeric and drop NaN rows."""
    df = df.copy()
    df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.dropna(subset=[col])


# ── KPI metadata ───────────────────────────────────────────────────────────────

KPI_LABELS = {
    'c1_visits':         'Visits',
    'c2_user':           'Users',
    'c3_pdoDeliver':     'PDO Deliveries',
    'c4_events':         'Training Events',
    'c6_eAttendees':     'Event Attendees',
    'c8_allEvent':       'All Events',
    'c10_pdoStored':     'PDO Stored',
    'c13_staff':         'Total Staff',
    'c14_nfunds':        'National Funds',
    'c15_cstaff':        'Contract Staff',
    'c16_cfunds':        'Contract Funds',
    'c19_pub':           'Publications',
}

# ── Data helper ────────────────────────────────────────────────────────────────

def prepare_by_kpi_all_countries(
    df: pd.DataFrame,
    kpis: list[str],
) -> pd.DataFrame:
    """
    Aggregate per country + year, melt into long format grouped by KPI.
    Returns columns: year, countryname, kpi, value
    """
    frames = []
    for col in kpis:
        tmp = clean_column(df.copy(), col)
        agg = tmp.groupby(['countryname', 'year'])[col].sum().reset_index()
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
    """
    One panel per KPI for a single country.
    Expects long-format DataFrame with columns: year, countryname, kpi, value
    """
    country_data = data[data['countryname'] == country]

    encode = dict(
        x=alt.X('year:O', title=None),
        y=alt.Y('value:Q', title=None, axis=alt.Axis(tickCount=3, grid=False)),
    )

    line = alt.Chart(country_data).mark_line(color='steelblue').encode(**encode)
    dots = alt.Chart(country_data).mark_point(filled=True, size=50, color='steelblue').encode(**encode)

    return (
        (line + dots)
        .properties(width=300)
        .facet(
            facet=alt.Facet(
                'kpi:N',
                header=alt.Header(titleOrient='bottom', labelOrient='bottom'),
                title=None,
            ),
            columns=columns,
        )
        .resolve_scale(y='independent')
        .resolve_axis(x='independent')
        .properties(
            title=alt.TitleParams(
                text=title, fontSize=16, fontWeight='bold', anchor='middle'
            )
        )
        .configure_view(stroke=None)
    )
