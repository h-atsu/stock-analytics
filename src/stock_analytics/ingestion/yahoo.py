from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import pandas as pd
import yfinance as yf

from stock_analytics.ingestion.schemas import (
    YahooCoverage,
    yahoo_daily_bars_model,
)
from stock_analytics.ingestion.storage import (
    IngestionArtifact,
    store_yahoo_coverage,
    store_yahoo_daily_bars,
)

BATCH_SIZE = 100
RETRY_DELAYS = (2, 4, 8)
OUTPUT_COLUMNS = [
    "trade_date",
    "yahoo_ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "dividends",
    "stock_splits",
    "capital_gains",
]
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]
COLUMN_NAMES = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "stock_splits",
    "Capital Gains": "capital_gains",
}

Download = Callable[[Sequence[str], date, date], pd.DataFrame]
Sleep = Callable[[float], None]


@dataclass(frozen=True)
class YahooIngestionResult:
    data_artifacts: tuple[IngestionArtifact, ...]
    coverage_artifact: IngestionArtifact
    row_count: int
    available_ticker_count: int
    no_data_ticker_count: int


def load_latest_yahoo_tickers(listed_issues_root: Path) -> list[str]:
    paths = sorted(
        (listed_issues_root / "listed_issues").glob(
            "snapshot_date=*/ingested_at=*/data.parquet"
        )
    )
    if not paths:
        raise FileNotFoundError("JPX上場銘柄一覧のParquetが見つかりません")

    frame = pd.read_parquet(paths[-1], columns=["yahoo_ticker"])
    tickers = sorted(frame["yahoo_ticker"].dropna().astype(str).unique().tolist())
    if not tickers:
        raise ValueError("Yahoo ticker候補がありません")
    return tickers


def _download_batch(
    tickers: Sequence[str], start_date: date, end_date: date
) -> pd.DataFrame:
    result = yf.download(
        list(tickers),
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=True,
        keepna=True,
        repair=False,
        threads=True,
        progress=False,
        timeout=30,
        multi_level_index=True,
    )
    if result is None:
        return pd.DataFrame()
    return result


def _download_with_retry(
    tickers: Sequence[str],
    start_date: date,
    end_date: date,
    download: Download,
    sleep: Sleep,
) -> pd.DataFrame:
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return download(tickers, start_date, end_date)
        except Exception:
            if attempt == len(RETRY_DELAYS):
                raise
            sleep(RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


def normalize_yahoo_download(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            {column: pd.Series(dtype=object) for column in OUTPUT_COLUMNS}
        )
    if (
        not isinstance(frame.columns, pd.MultiIndex)
        or "Ticker" not in frame.columns.names
    ):
        raise ValueError("yfinanceの列構造が想定と異なります")

    normalized = (
        frame.rename_axis(index="trade_date")
        .stack(level="Ticker", future_stack=True)
        .rename(columns=COLUMN_NAMES)
        .rename_axis(index=["trade_date", "yahoo_ticker"])
        .reset_index()
    )
    normalized.columns.name = None
    for column in OUTPUT_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    normalized = normalized[OUTPUT_COLUMNS]
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"])
    for column in OUTPUT_COLUMNS[2:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").astype(
            float
        )
    return normalized


def _coverage(
    tickers: Sequence[str],
    frame: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    usable = (
        frame[PRICE_COLUMNS].notna().any(axis=1)
        if not frame.empty
        else pd.Series(dtype=bool)
    )
    counts = frame.loc[usable].groupby("yahoo_ticker").size().to_dict()
    coverage = pd.DataFrame(
        {
            "yahoo_ticker": list(tickers),
            "row_count": [int(counts.get(ticker, 0)) for ticker in tickers],
            "start_date": pd.Timestamp(start_date),
            "end_date": pd.Timestamp(end_date),
        }
    )
    coverage["status"] = (
        coverage["row_count"].gt(0).map({True: "available", False: "no_data"})
    )
    return coverage[["yahoo_ticker", "status", "row_count", "start_date", "end_date"]]


def ingest_yahoo_daily_bars(
    tickers: Sequence[str],
    start_date: date,
    end_date: date,
    output_root: Path,
    *,
    download: Download | None = None,
    sleep: Sleep = time.sleep,
    ingested_at: datetime | None = None,
) -> YahooIngestionResult:
    if start_date > end_date:
        raise ValueError("start_dateはend_date以前にしてください")
    unique_tickers = sorted(set(tickers))
    if not unique_tickers:
        raise ValueError("取得対象tickerがありません")

    downloader = download or _download_batch
    frames: list[pd.DataFrame] = []
    for offset in range(0, len(unique_tickers), BATCH_SIZE):
        batch = unique_tickers[offset : offset + BATCH_SIZE]
        response = _download_with_retry(batch, start_date, end_date, downloader, sleep)
        frames.append(normalize_yahoo_download(response))

    combined = pd.concat(frames, ignore_index=True)
    if not combined.empty:
        in_range = combined["trade_date"].dt.date.between(start_date, end_date)
        combined = combined.loc[in_range].reset_index(drop=True)

    timestamp = ingested_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("ingested_at must be timezone-aware")
    timestamp = timestamp.astimezone(UTC)

    artifacts: list[IngestionArtifact] = []
    if not combined.empty:
        for group_key, daily_frame in combined.groupby(combined["trade_date"].dt.date):
            trade_date = cast(date, group_key)
            validated = yahoo_daily_bars_model(trade_date).validate(
                daily_frame.reset_index(drop=True), lazy=True
            )
            artifacts.append(
                store_yahoo_daily_bars(
                    validated,
                    trade_date,
                    output_root,
                    ingested_at=timestamp,
                )
            )

    coverage = YahooCoverage.validate(
        _coverage(unique_tickers, combined, start_date, end_date), lazy=True
    )
    coverage_artifact = store_yahoo_coverage(
        coverage,
        start_date,
        end_date,
        output_root,
        ingested_at=timestamp,
    )
    available_count = int(coverage["status"].eq("available").sum())
    return YahooIngestionResult(
        data_artifacts=tuple(artifacts),
        coverage_artifact=coverage_artifact,
        row_count=len(combined),
        available_ticker_count=available_count,
        no_data_ticker_count=len(coverage) - available_count,
    )
