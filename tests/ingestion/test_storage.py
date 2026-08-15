import hashlib
import json
from datetime import UTC, date, datetime

import pandas as pd

from stock_analytics.ingestion.storage import store_daily_bars, store_equity_master
from tests.ingestion.test_schemas import valid_daily_bars, valid_equity_master


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
