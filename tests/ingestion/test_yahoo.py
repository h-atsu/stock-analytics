from datetime import UTC, date, datetime

import pandas as pd

from stock_analytics.ingestion.yahoo import (
    _download_batch,
    ingest_yahoo_daily_bars,
    load_latest_yahoo_tickers,
    normalize_yahoo_download,
)


def yahoo_response() -> pd.DataFrame:
    index = pd.to_datetime(["2026-08-03", "2026-08-04"])
    columns = pd.MultiIndex.from_tuples(
        [
            ("Adj Close", "1301.T"),
            ("Capital Gains", "1301.T"),
            ("Close", "1301.T"),
            ("Dividends", "1301.T"),
            ("High", "1301.T"),
            ("Low", "1301.T"),
            ("Open", "1301.T"),
            ("Stock Splits", "1301.T"),
            ("Volume", "1301.T"),
        ],
        names=["Price", "Ticker"],
    )
    return pd.DataFrame(
        [
            [104.0, 0.0, 105.0, 0.0, 110.0, 95.0, 100.0, 0.0, 1000],
            [105.0, 1.0, 106.0, 5.0, 111.0, 96.0, 101.0, 2.0, 1200],
        ],
        index=index,
        columns=columns,
    ).rename_axis(index="Date")


def test_normalize_yahoo_download_preserves_prices_and_actions() -> None:
    normalized = normalize_yahoo_download(yahoo_response())

    assert normalized["yahoo_ticker"].unique().tolist() == ["1301.T"]
    assert normalized["dividends"].tolist() == [0.0, 5.0]
    assert normalized["stock_splits"].tolist() == [0.0, 2.0]
    assert normalized["capital_gains"].tolist() == [0.0, 1.0]


def test_download_batch_converts_inclusive_end_date(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_download(tickers, **kwargs):
        captured["tickers"] = tickers
        captured.update(kwargs)
        return yahoo_response()

    monkeypatch.setattr("stock_analytics.ingestion.yahoo.yf.download", fake_download)

    _download_batch(["1301.T"], date(2026, 8, 3), date(2026, 8, 10))

    assert captured["start"] == "2026-08-03"
    assert captured["end"] == "2026-08-11"
    assert captured["auto_adjust"] is False
    assert captured["actions"] is True
    assert captured["threads"] is True


def test_load_latest_yahoo_tickers_uses_latest_jpx_snapshot(tmp_path) -> None:
    older = (
        tmp_path
        / "listed_issues"
        / "snapshot_date=2026-06-30"
        / "ingested_at=20260703T000000.000000Z"
    )
    latest = (
        tmp_path
        / "listed_issues"
        / "snapshot_date=2026-07-31"
        / "ingested_at=20260805T000000.000000Z"
    )
    older.mkdir(parents=True)
    latest.mkdir(parents=True)
    pd.DataFrame({"yahoo_ticker": ["1301.T"]}).to_parquet(
        older / "data.parquet", index=False
    )
    pd.DataFrame({"yahoo_ticker": ["7203.T", None, "1301.T"]}).to_parquet(
        latest / "data.parquet", index=False
    )

    assert load_latest_yahoo_tickers(tmp_path) == ["1301.T", "7203.T"]


def test_ingest_yahoo_daily_bars_retries_and_records_no_data(tmp_path) -> None:
    attempts = 0
    delays: list[float] = []

    def flaky_download(tickers, start_date, end_date):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary")
        return yahoo_response()

    result = ingest_yahoo_daily_bars(
        ["1301.T", "9999.T"],
        date(2026, 8, 3),
        date(2026, 8, 4),
        tmp_path,
        download=flaky_download,
        sleep=delays.append,
        ingested_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
    )

    assert attempts == 3
    assert delays == [2, 4]
    assert result.row_count == 2
    assert len(result.data_artifacts) == 2
    assert result.available_ticker_count == 1
    assert result.no_data_ticker_count == 1
    coverage = pd.read_parquet(result.coverage_artifact.data_path)
    assert coverage.set_index("yahoo_ticker")["status"].to_dict() == {
        "1301.T": "available",
        "9999.T": "no_data",
    }
