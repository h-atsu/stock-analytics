from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

DATASET_NAME = "equity_daily_bars"
SOURCE_ENDPOINT = "/equities/bars/daily"
EQUITY_MASTER_DATASET_NAME = "equity_master"
EQUITY_MASTER_SOURCE_ENDPOINT = "/equities/master"
FINANCIAL_SUMMARY_DATASET_NAME = "financial_summary"
FINANCIAL_SUMMARY_SOURCE_ENDPOINT = "/fins/summary"
EARNINGS_DATE_DATASET_NAME = "earnings_date"
EARNINGS_DATE_SOURCE_ENDPOINT = "/fins/earnings-date"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class IngestionArtifact:
    data_path: Path
    manifest_path: Path
    row_count: int


@dataclass(frozen=True)
class ListedIssuesArtifact:
    source_path: Path
    data_path: Path
    manifest_path: Path
    row_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write_bytes_atomically(content: bytes, target: Path) -> None:
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=".source-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(content)

    try:
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_parquet_atomically(frame: pd.DataFrame, target: Path) -> None:
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=".data-",
        suffix=".parquet.tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        frame.to_parquet(temporary_path, index=False, engine="pyarrow")
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_json_atomically(payload: dict[str, object], target: Path) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=".manifest-",
        suffix=".json.tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        json.dump(payload, temporary, ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write("\n")

    try:
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def _store_date_partition(
    frame: pd.DataFrame,
    partition_date: date,
    output_root: Path,
    *,
    dataset_name: str,
    source_endpoint: str,
    partition_name: str,
    date_column: str,
    ingested_at: datetime | None = None,
) -> IngestionArtifact:
    timestamp = ingested_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("ingested_at must be timezone-aware")
    timestamp = timestamp.astimezone(UTC)

    run_partition = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = (
        output_root
        / dataset_name
        / f"{partition_name}={partition_date.isoformat()}"
        / f"ingested_at={run_partition}"
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    stored_frame = frame.copy()
    stored_frame[date_column] = pd.to_datetime(stored_frame[date_column]).dt.date
    stored_frame["_ingested_at"] = timestamp
    stored_frame["_source"] = source_endpoint

    data_path = output_dir / "data.parquet"
    manifest_path = output_dir / "manifest.json"
    _write_parquet_atomically(stored_frame, data_path)

    manifest: dict[str, object] = {
        "dataset": dataset_name,
        partition_name: partition_date.isoformat(),
        "ingested_at": timestamp.isoformat().replace("+00:00", "Z"),
        "row_count": len(stored_frame),
        "source": source_endpoint,
        "schema_version": SCHEMA_VERSION,
        "sha256": _sha256(data_path),
    }
    _write_json_atomically(manifest, manifest_path)

    return IngestionArtifact(
        data_path=data_path,
        manifest_path=manifest_path,
        row_count=len(stored_frame),
    )


def store_daily_bars(
    frame: pd.DataFrame,
    trade_date: date,
    output_root: Path,
    *,
    ingested_at: datetime | None = None,
) -> IngestionArtifact:
    return _store_date_partition(
        frame,
        trade_date,
        output_root,
        dataset_name=DATASET_NAME,
        source_endpoint=SOURCE_ENDPOINT,
        partition_name="trade_date",
        date_column="Date",
        ingested_at=ingested_at,
    )


def store_equity_master(
    frame: pd.DataFrame,
    snapshot_date: date,
    output_root: Path,
    *,
    ingested_at: datetime | None = None,
) -> IngestionArtifact:
    return _store_date_partition(
        frame,
        snapshot_date,
        output_root,
        dataset_name=EQUITY_MASTER_DATASET_NAME,
        source_endpoint=EQUITY_MASTER_SOURCE_ENDPOINT,
        partition_name="snapshot_date",
        date_column="Date",
        ingested_at=ingested_at,
    )


def store_financial_summary(
    frame: pd.DataFrame,
    disclosure_date: date,
    output_root: Path,
    *,
    ingested_at: datetime | None = None,
) -> IngestionArtifact:
    return _store_date_partition(
        frame,
        disclosure_date,
        output_root,
        dataset_name=FINANCIAL_SUMMARY_DATASET_NAME,
        source_endpoint=FINANCIAL_SUMMARY_SOURCE_ENDPOINT,
        partition_name="disclosure_date",
        date_column="DiscDate",
        ingested_at=ingested_at,
    )


def store_earnings_date(
    frame: pd.DataFrame,
    publication_date: date,
    output_root: Path,
    *,
    ingested_at: datetime | None = None,
) -> IngestionArtifact:
    return _store_date_partition(
        frame,
        publication_date,
        output_root,
        dataset_name=EARNINGS_DATE_DATASET_NAME,
        source_endpoint=EARNINGS_DATE_SOURCE_ENDPOINT,
        partition_name="publication_date",
        date_column="PubDate",
        ingested_at=ingested_at,
    )


def _has_source_hash(dataset_root: Path, source_hash: str) -> bool:
    for manifest_path in dataset_root.glob(
        "snapshot_date=*/ingested_at=*/manifest.json"
    ):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source_sha256") == source_hash:
            return True
    return False


def store_jpx_listed_issues(
    frame: pd.DataFrame,
    source_content: bytes,
    source_url: str,
    output_root: Path,
    *,
    ingested_at: datetime | None = None,
) -> ListedIssuesArtifact | None:
    source_hash = _sha256_bytes(source_content)
    dataset_root = output_root / "listed_issues"
    if _has_source_hash(dataset_root, source_hash):
        return None

    timestamp = ingested_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("ingested_at must be timezone-aware")
    timestamp = timestamp.astimezone(UTC)

    snapshot_dates = pd.to_datetime(frame["snapshot_date"]).dt.date.unique()
    if len(snapshot_dates) != 1:
        raise ValueError("snapshot_date must contain exactly one date")
    snapshot_date = snapshot_dates[0]

    run_partition = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = (
        dataset_root
        / f"snapshot_date={snapshot_date.isoformat()}"
        / f"ingested_at={run_partition}"
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    stored_frame = frame.copy()
    stored_frame["snapshot_date"] = pd.to_datetime(
        stored_frame["snapshot_date"]
    ).dt.date
    stored_frame["_ingested_at"] = timestamp
    stored_frame["_source"] = source_url

    source_path = output_dir / "source.xls"
    data_path = output_dir / "data.parquet"
    manifest_path = output_dir / "manifest.json"
    _write_bytes_atomically(source_content, source_path)
    _write_parquet_atomically(stored_frame, data_path)

    manifest: dict[str, object] = {
        "dataset": "listed_issues",
        "snapshot_date": snapshot_date.isoformat(),
        "ingested_at": timestamp.isoformat().replace("+00:00", "Z"),
        "row_count": len(stored_frame),
        "source": source_url,
        "source_sha256": source_hash,
        "schema_version": SCHEMA_VERSION,
        "sha256": _sha256(data_path),
    }
    _write_json_atomically(manifest, manifest_path)

    return ListedIssuesArtifact(
        source_path=source_path,
        data_path=data_path,
        manifest_path=manifest_path,
        row_count=len(stored_frame),
    )


def store_yahoo_daily_bars(
    frame: pd.DataFrame,
    trade_date: date,
    output_root: Path,
    *,
    ingested_at: datetime,
) -> IngestionArtifact:
    return _store_date_partition(
        frame,
        trade_date,
        output_root,
        dataset_name="equity_daily_bars",
        source_endpoint="yfinance.download",
        partition_name="trade_date",
        date_column="trade_date",
        ingested_at=ingested_at,
    )


def store_yahoo_coverage(
    frame: pd.DataFrame,
    start_date: date,
    end_date: date,
    output_root: Path,
    *,
    ingested_at: datetime,
) -> IngestionArtifact:
    timestamp = ingested_at.astimezone(UTC)
    run_partition = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = (
        output_root
        / "equity_daily_bars_coverage"
        / f"start_date={start_date.isoformat()}"
        / f"end_date={end_date.isoformat()}"
        / f"ingested_at={run_partition}"
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    stored_frame = frame.copy()
    stored_frame["start_date"] = pd.to_datetime(stored_frame["start_date"]).dt.date
    stored_frame["end_date"] = pd.to_datetime(stored_frame["end_date"]).dt.date
    stored_frame["_ingested_at"] = timestamp
    stored_frame["_source"] = "yfinance.download"

    data_path = output_dir / "data.parquet"
    manifest_path = output_dir / "manifest.json"
    _write_parquet_atomically(stored_frame, data_path)
    manifest: dict[str, object] = {
        "dataset": "equity_daily_bars_coverage",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ingested_at": timestamp.isoformat().replace("+00:00", "Z"),
        "row_count": len(stored_frame),
        "source": "yfinance.download",
        "schema_version": SCHEMA_VERSION,
        "sha256": _sha256(data_path),
    }
    _write_json_atomically(manifest, manifest_path)
    return IngestionArtifact(
        data_path=data_path,
        manifest_path=manifest_path,
        row_count=len(stored_frame),
    )
