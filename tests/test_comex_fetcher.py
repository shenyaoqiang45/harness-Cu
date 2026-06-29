"""Tests for CME COMEX copper stocks parser."""

from datetime import date

from copper_forecast.fetchers.comex import parse_cme_copper_stocks_xls


def test_parse_cme_copper_stocks_xls_from_fixture():
    # Minimal XLS-like content built as HTML table saved - use live fetch sample bytes
    import io

    import pandas as pd

    rows = [
        [None] * 9,
        [None, None, None, None, None, None, None, "Activity Date: 6/25/2026", None],
        [None] * 9,
        ["TOTAL COPPER", 660768, 3145, 1111, 2034, 0, 662802, None, None],
    ]
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False, header=False)
    buffer.seek(0)

    activity_date, metric_tons = parse_cme_copper_stocks_xls(buffer.read())
    assert activity_date == date(2026, 6, 25)
    assert metric_tons == round(662802 * 0.90718474, 2)
