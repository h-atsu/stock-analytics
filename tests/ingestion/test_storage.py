import hashlib
import json
from datetime import UTC, date, datetime

import pandas as pd

from stock_analytics.ingestion.storage import (
    store_daily_bars,
    store_earnings_date,
    store_equity_master,
    store_financial_summary,
    store_jpx_listed_issues,
)
from tests.ingestion.test_schemas import (
    valid_daily_bars,
    valid_earnings_date,
    valid_equity_master,
    valid_financial_summary,
    valid_jpx_listed_issues,
)


def test_store_daily_bars_writes_partitioned_parquet_and_manifest(tmp_path) -> None:
    ingested_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    artifact = store_daily_bars(
        valid_daily_bars(),
        date(2024, 7, 25),
        tmp_path,
        ingested_at=ingested_at,
    )

    assert artifact.data_path == (
        tmp_path
        / "equity_daily_bars"
        / "trade_date=2024-07-25"
        / "ingested_at=20260815T120000.000000Z"
        / "data.parquet"
    )
    stored = pd.read_parquet(artifact.data_path)
    assert len(stored) == 2
    assert stored["Code"].tolist() == ["13010", "13020"]
    assert stored["_source"].unique().tolist() == ["/equities/bars/daily"]
    assert str(stored["Date"].dtype) == "object"

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(artifact.data_path.read_bytes()).hexdigest()
    assert manifest == {
        "dataset": "equity_daily_bars",
        "ingested_at": "2026-08-15T12:00:00Z",
        "row_count": 2,
        "schema_version": 1,
        "sha256": expected_hash,
        "source": "/equities/bars/daily",
        "trade_date": "2024-07-25",
    }


def test_store_equity_master_writes_snapshot_parquet_and_manifest(tmp_path) -> None:
    ingested_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    artifact = store_equity_master(
        valid_equity_master(),
        date(2024, 7, 25),
        tmp_path,
        ingested_at=ingested_at,
    )

    assert artifact.data_path == (
        tmp_path
        / "equity_master"
        / "snapshot_date=2024-07-25"
        / "ingested_at=20260815T120000.000000Z"
        / "data.parquet"
    )
    stored = pd.read_parquet(artifact.data_path)
    assert stored["Code"].tolist() == ["13010", "130A0"]
    assert stored["_source"].unique().tolist() == ["/equities/master"]

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(artifact.data_path.read_bytes()).hexdigest()
    assert manifest == {
        "dataset": "equity_master",
        "ingested_at": "2026-08-15T12:00:00Z",
        "row_count": 2,
        "schema_version": 1,
        "sha256": expected_hash,
        "snapshot_date": "2024-07-25",
        "source": "/equities/master",
    }


def test_store_financial_summary_writes_disclosure_partition(tmp_path) -> None:
    ingested_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    artifact = store_financial_summary(
        valid_financial_summary(),
        date(2024, 7, 25),
        tmp_path,
        ingested_at=ingested_at,
    )

    assert artifact.data_path == (
        tmp_path
        / "financial_summary"
        / "disclosure_date=2024-07-25"
        / "ingested_at=20260815T120000.000000Z"
        / "data.parquet"
    )
    stored = pd.read_parquet(artifact.data_path)
    assert stored["DiscNo"].tolist() == ["20240725555555", "20240725666666"]
    assert stored["_source"].unique().tolist() == ["/fins/summary"]

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(artifact.data_path.read_bytes()).hexdigest()
    assert manifest == {
        "dataset": "financial_summary",
        "disclosure_date": "2024-07-25",
        "ingested_at": "2026-08-15T12:00:00Z",
        "row_count": 2,
        "schema_version": 1,
        "sha256": expected_hash,
        "source": "/fins/summary",
    }


def test_store_earnings_date_writes_publication_partition(tmp_path) -> None:
    ingested_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    artifact = store_earnings_date(
        valid_earnings_date(),
        date(2024, 7, 25),
        tmp_path,
        ingested_at=ingested_at,
    )

    assert artifact.data_path == (
        tmp_path
        / "earnings_date"
        / "publication_date=2024-07-25"
        / "ingested_at=20260815T120000.000000Z"
        / "data.parquet"
    )
    stored = pd.read_parquet(artifact.data_path)
    assert stored["FQName"].tolist() == ["FY", "1Q"]
    assert stored["_source"].unique().tolist() == ["/fins/earnings-date"]

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(artifact.data_path.read_bytes()).hexdigest()
    assert manifest == {
        "dataset": "earnings_date",
        "ingested_at": "2026-08-15T12:00:00Z",
        "publication_date": "2024-07-25",
        "row_count": 2,
        "schema_version": 1,
        "sha256": expected_hash,
        "source": "/fins/earnings-date",
    }


def test_store_jpx_listed_issues_writes_source_and_skips_same_hash(tmp_path) -> None:
    ingested_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    source_content = b"source excel"
    source_url = "https://www.jpx.co.jp/example/data_j.xls"

    artifact = store_jpx_listed_issues(
        valid_jpx_listed_issues(),
        source_content,
        source_url,
        tmp_path,
        ingested_at=ingested_at,
    )

    assert artifact is not None
    assert artifact.source_path.read_bytes() == source_content
    assert artifact.data_path == (
        tmp_path
        / "listed_issues"
        / "snapshot_date=2026-07-31"
        / "ingested_at=20260815T120000.000000Z"
        / "data.parquet"
    )
    stored = pd.read_parquet(artifact.data_path)
    assert stored["security_code"].tolist() == ["1301", "25935"]
    assert stored["_source"].unique().tolist() == [source_url]

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(artifact.data_path.read_bytes()).hexdigest()
    assert manifest == {
        "dataset": "listed_issues",
        "ingested_at": "2026-08-15T12:00:00Z",
        "row_count": 2,
        "schema_version": 1,
        "sha256": expected_hash,
        "snapshot_date": "2026-07-31",
        "source": source_url,
        "source_sha256": hashlib.sha256(source_content).hexdigest(),
    }

    duplicate = store_jpx_listed_issues(
        valid_jpx_listed_issues(),
        source_content,
        source_url,
        tmp_path,
        ingested_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
    )
    assert duplicate is None
