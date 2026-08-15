from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, cast

import jquantsapi
import requests

from stock_analytics.ingestion.jpx import ingest_listed_issues
from stock_analytics.ingestion.jquants import (
    DailyBarsClient,
    EarningsDateClient,
    EquityMasterClient,
    FinancialSummaryClient,
    ingest_daily_bars,
    ingest_earnings_date,
    ingest_equity_master,
    ingest_financial_summary,
)
from stock_analytics.ingestion.yahoo import (
    ingest_yahoo_daily_bars,
    load_latest_yahoo_tickers,
)
from stock_analytics.publishing.bigquery import (
    BigQueryLoadResult,
    load_all_raw_artifacts,
)
from stock_analytics.publishing.gcs import GcsPublishResult, publish_raw_artifacts

JQUANTS_DELAY = timedelta(weeks=12)
JQUANTS_YEARS = 2
YAHOO_YEARS = 5
MASTER_LOOKBACK_DAYS = 10
JQUANTS_REQUEST_INTERVAL_SECONDS = 2.0
JQUANTS_RATE_LIMIT_DELAYS = (60.0, 120.0, 240.0)

Progress = Callable[[str], None]
Sleep = Callable[[float], None]


class BootstrapJQuantsClient(
    DailyBarsClient,
    EquityMasterClient,
    FinancialSummaryClient,
    EarningsDateClient,
    Protocol,
):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    fetched_artifact_count: int
    skipped_partition_count: int
    no_data_count: int
    yahoo_row_count: int
    publish_result: GcsPublishResult
    load_result: BigQueryLoadResult


def years_before(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def _weekdays(start_date: date, end_date: date) -> Iterator[date]:
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def _has_partition(
    root: Path,
    dataset_name: str,
    partition_name: str,
    partition_date: date,
) -> bool:
    partition = root / dataset_name / f"{partition_name}={partition_date.isoformat()}"
    return _has_valid_runs(partition)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_valid_runs(partition: Path) -> bool:
    manifests = list(partition.glob("ingested_at=*/manifest.json"))
    for manifest_path in manifests:
        data_path = manifest_path.with_name("data.parquet")
        if not data_path.is_file():
            raise FileNotFoundError(
                f"manifestに対応するParquetがありません: {data_path}"
            )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != _sha256(data_path):
            raise ValueError(f"ParquetのSHA-256がmanifestと一致しません: {data_path}")
    return bool(manifests)


def _has_valid_partitioned_dataset(root: Path, partition_name: str) -> bool:
    partitions = list(root.glob(f"{partition_name}=*"))
    return any(_has_valid_runs(partition) for partition in partitions)


def _has_yahoo_run(root: Path, start_date: date, end_date: date) -> bool:
    run = (
        root
        / "equity_daily_bars_coverage"
        / f"start_date={start_date.isoformat()}"
        / f"end_date={end_date.isoformat()}"
    )
    return _has_valid_runs(run)


def _request_jquants[T](
    request: Callable[[], T],
    progress: Progress,
    sleep: Sleep,
) -> T:
    for attempt in range(len(JQUANTS_RATE_LIMIT_DELAYS) + 1):
        try:
            result = request()
        except requests.RequestException as exc:
            if "429" not in str(exc) or attempt == len(JQUANTS_RATE_LIMIT_DELAYS):
                raise
            delay = JQUANTS_RATE_LIMIT_DELAYS[attempt]
            progress(f"J-Quants rate limit: {delay:.0f}秒待機して再試行します")
            sleep(delay)
            continue
        sleep(JQUANTS_REQUEST_INTERVAL_SECONDS)
        return result
    raise AssertionError("unreachable")


def bootstrap_raw(
    as_of: date,
    project_id: str,
    bucket_name: str,
    output_root: Path = Path("data/raw"),
    dataset_id: str = "stock_analytics",
    *,
    jquants_start_date: date | None = None,
    yahoo_start_date: date | None = None,
    jquants_client: BootstrapJQuantsClient | None = None,
    progress: Progress = lambda _message: None,
    sleep: Sleep = time.sleep,
) -> BootstrapResult:
    """Build the initial local, GCS, and BigQuery raw dataset."""
    jquants_end_date = as_of - JQUANTS_DELAY
    jquants_start = jquants_start_date or years_before(jquants_end_date, JQUANTS_YEARS)
    yahoo_start = yahoo_start_date or years_before(as_of, YAHOO_YEARS)
    if jquants_start > jquants_end_date:
        raise ValueError("J-Quantsの開始日は終了日以前にしてください")
    if yahoo_start > as_of:
        raise ValueError("Yahooの開始日はas-of以前にしてください")

    jpx_root = output_root / "jpx"
    jquants_root = output_root / "jquants"
    yahoo_root = output_root / "yfinance"
    client = jquants_client or cast(BootstrapJQuantsClient, jquantsapi.ClientV2())
    fetched = 0
    skipped = 0
    no_data = 0

    progress("JPX現行上場銘柄一覧を取得します")
    listed_issues = ingest_listed_issues(jpx_root)
    if listed_issues is None:
        if not _has_valid_partitioned_dataset(
            jpx_root / "listed_issues", "snapshot_date"
        ):
            raise RuntimeError("保存済みJPX上場銘柄一覧を確認できませんでした")
        skipped += 1
    else:
        fetched += 1

    progress("J-Quants銘柄マスターを取得します")
    master_date = jquants_end_date
    master_loaded = False
    for _ in range(MASTER_LOOKBACK_DAYS + 1):
        if master_date.weekday() >= 5:
            master_date -= timedelta(days=1)
            continue
        if _has_partition(jquants_root, "equity_master", "snapshot_date", master_date):
            skipped += 1
            master_loaded = True
            break
        artifact = _request_jquants(
            lambda master_date=master_date: ingest_equity_master(
                master_date, jquants_root, client=client
            ),
            progress,
            sleep,
        )
        if artifact is not None:
            fetched += 1
            master_loaded = True
            break
        no_data += 1
        master_date -= timedelta(days=1)
    if not master_loaded:
        raise RuntimeError("J-Quants銘柄マスターを直近10日から取得できませんでした")

    weekdays = list(_weekdays(jquants_start, jquants_end_date))
    progress(
        f"J-Quants日足・財務・決算予定を取得します: "
        f"{jquants_start}..{jquants_end_date} ({len(weekdays)} weekdays)"
    )
    jobs = (
        ("equity_daily_bars", "trade_date", ingest_daily_bars),
        ("financial_summary", "disclosure_date", ingest_financial_summary),
        ("earnings_date", "publication_date", ingest_earnings_date),
    )
    for index, target_date in enumerate(weekdays, start=1):
        for dataset_name, partition_name, ingest in jobs:
            if _has_partition(jquants_root, dataset_name, partition_name, target_date):
                skipped += 1
                continue
            artifact = _request_jquants(
                lambda ingest=ingest, target_date=target_date: ingest(
                    target_date, jquants_root, client=client
                ),
                progress,
                sleep,
            )
            if artifact is None:
                no_data += 1
            else:
                fetched += 1
        if index % 25 == 0 or index == len(weekdays):
            progress(f"J-Quants進捗: {index}/{len(weekdays)} weekdays")

    progress(f"Yahoo Finance日足を取得します: {yahoo_start}..{as_of}")
    yahoo_rows = 0
    if _has_yahoo_run(yahoo_root, yahoo_start, as_of):
        skipped += 1
    else:
        tickers = load_latest_yahoo_tickers(jpx_root)
        yahoo_result = ingest_yahoo_daily_bars(tickers, yahoo_start, as_of, yahoo_root)
        fetched += len(yahoo_result.data_artifacts) + 1
        yahoo_rows = yahoo_result.row_count

    progress("検証済みraw artifactをGCSへpublishします")
    publish_result = publish_raw_artifacts(output_root, bucket_name)
    progress("全raw artifactをBigQueryへloadします")
    load_result = load_all_raw_artifacts(bucket_name, project_id, dataset_id)

    return BootstrapResult(
        fetched_artifact_count=fetched,
        skipped_partition_count=skipped,
        no_data_count=no_data,
        yahoo_row_count=yahoo_rows,
        publish_result=publish_result,
        load_result=load_result,
    )
