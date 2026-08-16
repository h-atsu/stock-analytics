import hashlib
import json
from datetime import date
from pathlib import Path
from typing import cast

import requests

from stock_analytics.bootstrap import (
    BootstrapJQuantsClient,
    _request_jquants,
    bootstrap_raw,
    years_before,
)
from stock_analytics.ingestion.storage import IngestionArtifact, ListedIssuesArtifact
from stock_analytics.ingestion.yahoo import YahooIngestionResult
from stock_analytics.publishing.bigquery import BigQueryLoadResult
from stock_analytics.publishing.gcs import GcsPublishResult


def test_years_before_handles_leap_day() -> None:
    assert years_before(date(2024, 2, 29), 5) == date(2019, 2, 28)


def test_jquants_request_waits_and_retries_429() -> None:
    attempts = 0
    sleeps: list[float] = []
    messages: list[str] = []

    def request() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise requests.exceptions.RetryError("too many 429error responses")
        return "ok"

    result = _request_jquants(request, messages.append, sleeps.append)

    assert result == "ok"
    assert attempts == 2
    assert sleeps == [60.0, 13.0]
    assert "60秒待機" in messages[0]


def test_bootstrap_raw_runs_fetch_publish_and_load(monkeypatch, tmp_path: Path) -> None:
    artifact = IngestionArtifact(
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=1,
    )
    listed = ListedIssuesArtifact(
        source_path=tmp_path / "source.xls",
        data_path=artifact.data_path,
        manifest_path=artifact.manifest_path,
        row_count=1,
    )
    requested: list[tuple[str, date]] = []

    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_listed_issues", lambda _root: listed
    )

    def fake_ingest(target_date, _root, *, client):
        del client
        requested.append(("ingest", target_date))
        return artifact

    monkeypatch.setattr("stock_analytics.bootstrap.ingest_equity_master", fake_ingest)
    monkeypatch.setattr("stock_analytics.bootstrap.ingest_daily_bars", fake_ingest)
    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_financial_summary", fake_ingest
    )
    monkeypatch.setattr("stock_analytics.bootstrap.ingest_earnings_date", fake_ingest)
    monkeypatch.setattr(
        "stock_analytics.bootstrap.load_latest_yahoo_tickers",
        lambda _root: ["7203.T"],
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_yahoo_daily_bars",
        lambda *_args: YahooIngestionResult(
            data_artifacts=(artifact,),
            coverage_artifact=artifact,
            row_count=5,
            available_ticker_count=1,
            no_data_ticker_count=0,
        ),
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.publish_raw_artifacts",
        lambda *_args: GcsPublishResult(uploaded_count=10, skipped_count=0),
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.load_all_raw_artifacts",
        lambda *_args: BigQueryLoadResult(
            loaded_partition_count=6, loaded_row_count=60
        ),
    )
    messages: list[str] = []

    result = bootstrap_raw(
        date(2026, 8, 16),
        "test-project",
        "raw-bucket",
        tmp_path,
        jquants_start_date=date(2026, 5, 22),
        yahoo_start_date=date(2026, 8, 14),
        jquants_client=cast(BootstrapJQuantsClient, object()),
        progress=messages.append,
        sleep=lambda _seconds: None,
    )

    assert requested == [
        ("ingest", date(2026, 5, 22)),
        ("ingest", date(2026, 5, 22)),
        ("ingest", date(2026, 5, 22)),
        ("ingest", date(2026, 5, 22)),
    ]
    assert result.fetched_artifact_count == 7
    assert result.yahoo_row_count == 5
    assert result.publish_result.uploaded_count == 10
    assert result.load_result.loaded_partition_count == 6
    assert messages[-1] == "全raw artifactをBigQueryへloadします"


def test_bootstrap_raw_skips_completed_jquants_partitions(
    monkeypatch, tmp_path: Path
) -> None:
    jquants_root = tmp_path / "jquants"
    jpx_manifest = (
        tmp_path
        / "jpx/listed_issues/snapshot_date=2026-07-31/ingested_at=run/manifest.json"
    )
    jpx_manifest.parent.mkdir(parents=True)
    jpx_manifest.with_name("data.parquet").write_bytes(b"parquet")
    jpx_manifest.write_text(
        json.dumps({"sha256": hashlib.sha256(b"parquet").hexdigest()}),
        encoding="utf-8",
    )
    partition_specs = [
        ("equity_master", "snapshot_date"),
        ("equity_daily_bars", "trade_date"),
        ("financial_summary", "disclosure_date"),
        ("earnings_date", "publication_date"),
    ]
    for dataset_name, partition_name in partition_specs:
        manifest = (
            jquants_root
            / dataset_name
            / f"{partition_name}=2026-05-22"
            / "ingested_at=run"
            / "manifest.json"
        )
        manifest.parent.mkdir(parents=True)
        data = manifest.with_name("data.parquet")
        data.write_bytes(b"parquet")
        manifest.write_text(
            json.dumps({"sha256": hashlib.sha256(b"parquet").hexdigest()}),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_listed_issues", lambda _root: None
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.load_latest_yahoo_tickers",
        lambda _root: ["7203.T"],
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_yahoo_daily_bars",
        lambda *_args: YahooIngestionResult(
            data_artifacts=(),
            coverage_artifact=IngestionArtifact(
                tmp_path / "data.parquet", tmp_path / "manifest.json", 1
            ),
            row_count=0,
            available_ticker_count=0,
            no_data_ticker_count=1,
        ),
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.publish_raw_artifacts",
        lambda *_args: GcsPublishResult(0, 10),
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.load_all_raw_artifacts",
        lambda *_args: BigQueryLoadResult(4, 40),
    )

    def unexpected_ingest(*_args, **_kwargs):
        raise AssertionError("completed partition must be skipped")

    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_equity_master", unexpected_ingest
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_daily_bars", unexpected_ingest
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_financial_summary", unexpected_ingest
    )
    monkeypatch.setattr(
        "stock_analytics.bootstrap.ingest_earnings_date", unexpected_ingest
    )

    result = bootstrap_raw(
        date(2026, 8, 16),
        "test-project",
        "raw-bucket",
        tmp_path,
        jquants_start_date=date(2026, 5, 22),
        yahoo_start_date=date(2026, 8, 14),
        jquants_client=cast(BootstrapJQuantsClient, object()),
        sleep=lambda _seconds: None,
    )

    assert result.skipped_partition_count == 5
