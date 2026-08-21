from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, cast

import jquantsapi

from stock_analytics.bootstrap import _request_jquants
from stock_analytics.ingestion.jpx import ingest_listed_issues
from stock_analytics.ingestion.jquants import (
    DailyBarsClient,
    EarningsDateClient,
    FinancialSummaryClient,
    ingest_daily_bars,
    ingest_earnings_date,
    ingest_financial_summary,
)
from stock_analytics.ingestion.yahoo import (
    ingest_yahoo_daily_bars,
    load_latest_yahoo_tickers,
)
from stock_analytics.publishing.bigquery import (
    BigQueryLoadResult,
    load_daily_pipeline_artifacts,
)
from stock_analytics.publishing.gcs import (
    GcsPublishResult,
    publish_raw_artifacts,
    sync_latest_listed_issues_artifact,
)

JQUANTS_DELAY = timedelta(weeks=12)
YAHOO_LOOKBACK = timedelta(days=7)
DEFAULT_REGION = "asia-northeast1"

Progress = Callable[[str], None]
Sleep = Callable[[float], None]


class DailyPipelineJQuantsClient(
    DailyBarsClient,
    FinancialSummaryClient,
    EarningsDateClient,
    Protocol,
):
    pass


@dataclass(frozen=True)
class DailyPipelineResult:
    as_of: date
    jquants_date: date
    yahoo_start_date: date
    fetched_artifact_count: int
    skipped_artifact_count: int
    no_data_count: int
    yahoo_row_count: int
    yahoo_no_data_ticker_count: int
    duration_seconds: float
    publish_result: GcsPublishResult
    load_result: BigQueryLoadResult


def run_dbt_build(
    project_id: str,
    dataset_id: str,
    region: str,
    project_dir: Path,
) -> None:
    profile_path = project_dir / "profiles.yml"
    if not profile_path.is_file():
        raise FileNotFoundError(f"dbt profiles.ymlが見つかりません: {profile_path}")

    environment = os.environ.copy()
    environment.update(
        {
            "GCP_PROJECT_ID": project_id,
            "DBT_DATASET": dataset_id,
            "GCP_REGION": region,
        }
    )
    subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir),
        ],
        check=True,
        env=environment,
    )


def run_daily_pipeline(
    as_of: date,
    project_id: str,
    bucket_name: str,
    output_root: Path = Path("data/raw"),
    dataset_id: str = "stock_analytics",
    region: str = DEFAULT_REGION,
    *,
    dbt_project_dir: Path = Path("dbt"),
    jquants_client: DailyPipelineJQuantsClient | None = None,
    progress: Progress = lambda _message: None,
    sleep: Sleep = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> DailyPipelineResult:
    """Run one deterministic ingestion, publish, load, and dbt cycle."""
    started_at = clock()
    jquants_date = as_of - JQUANTS_DELAY
    yahoo_start_date = as_of - YAHOO_LOOKBACK
    jpx_root = output_root / "jpx"
    jquants_root = output_root / "jquants"
    yahoo_root = output_root / "yfinance"
    client = jquants_client or cast(DailyPipelineJQuantsClient, jquantsapi.ClientV2())

    progress("GCSから最新のJPX上場銘柄一覧を復元します")
    sync_latest_listed_issues_artifact(bucket_name, output_root)

    fetched = 0
    skipped = 0
    no_data = 0
    progress("JPX現行上場銘柄一覧のハッシュを確認します")
    listed_issues = ingest_listed_issues(jpx_root)
    if listed_issues is None:
        skipped += 1
    else:
        fetched += 1

    progress(f"J-Quants日次データを取得します: {jquants_date}")
    jquants_jobs = (
        ingest_daily_bars,
        ingest_financial_summary,
        ingest_earnings_date,
    )
    for ingest in jquants_jobs:
        artifact = _request_jquants(
            lambda ingest=ingest: ingest(jquants_date, jquants_root, client=client),
            progress,
            sleep,
        )
        if artifact is None:
            no_data += 1
        else:
            fetched += 1

    progress(f"Yahoo Finance日足を取得します: {yahoo_start_date}..{as_of}")
    tickers = load_latest_yahoo_tickers(jpx_root)
    yahoo_result = ingest_yahoo_daily_bars(
        tickers,
        yahoo_start_date,
        as_of,
        yahoo_root,
    )
    fetched += len(yahoo_result.data_artifacts) + 1

    progress("検証済みraw artifactをGCSへpublishします")
    publish_result = publish_raw_artifacts(output_root, bucket_name)
    progress("今回更新したraw partitionをBigQueryへloadします")
    load_result = load_daily_pipeline_artifacts(
        bucket_name,
        project_id,
        jquants_date,
        yahoo_start_date,
        as_of,
        dataset_id,
    )

    progress("dbt buildを実行します")
    run_dbt_build(project_id, dataset_id, region, dbt_project_dir)

    return DailyPipelineResult(
        as_of=as_of,
        jquants_date=jquants_date,
        yahoo_start_date=yahoo_start_date,
        fetched_artifact_count=fetched,
        skipped_artifact_count=skipped,
        no_data_count=no_data,
        yahoo_row_count=yahoo_result.row_count,
        yahoo_no_data_ticker_count=yahoo_result.no_data_ticker_count,
        duration_seconds=clock() - started_at,
        publish_result=publish_result,
        load_result=load_result,
    )
