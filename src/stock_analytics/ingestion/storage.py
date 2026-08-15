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
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class IngestionArtifact:
    data_path: Path
    manifest_path: Path
    row_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    stored_frame["Date"] = pd.to_datetime(stored_frame["Date"]).dt.date
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
        ingested_at=ingested_at,
    )
