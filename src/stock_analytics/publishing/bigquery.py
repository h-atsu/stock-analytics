from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, cast

from google.cloud import bigquery, storage

JQUANTS_PREFIX = "jquants/equity_daily_bars"
YFINANCE_PREFIX = "yfinance/equity_daily_bars"


@dataclass(frozen=True)
class BigQueryLoadResult:
    loaded_partition_count: int
    loaded_row_count: int


class BlobLike(Protocol):
    @property
    def name(self) -> str: ...


class StorageClientLike(Protocol):
    def list_blobs(self, bucket_name: str, *, prefix: str) -> Iterable[BlobLike]: ...


class LoadJobLike(Protocol):
    @property
    def output_rows(self) -> int | None: ...

    def result(self) -> object: ...


class BigQueryClientLike(Protocol):
    def load_table_from_uri(
        self,
        uris: list[str],
        destination: str,
        *,
        job_config: bigquery.LoadJobConfig,
    ) -> LoadJobLike: ...


def _completed_parquet_by_partition(
    storage_client: StorageClientLike,
    bucket_name: str,
    prefix: str,
    partition_name: str,
) -> dict[str, list[str]]:
    pattern = re.compile(
        rf"^{re.escape(prefix)}/{re.escape(partition_name)}="
        r"(\d{4}-\d{2}-\d{2})/(?:[^/]+/)*"
        r"ingested_at=[^/]+/manifest\.json$"
    )
    objects_by_date: defaultdict[str, list[str]] = defaultdict(list)

    for blob in storage_client.list_blobs(bucket_name, prefix=f"{prefix}/"):
        match = pattern.fullmatch(blob.name)
        if match is None:
            continue
        objects_by_date[match.group(1)].append(
            blob.name.removesuffix("manifest.json") + "data.parquet"
        )

    return {
        trade_date: sorted(object_names)
        for trade_date, object_names in sorted(objects_by_date.items())
    }


def _load_partitions(
    bigquery_client: BigQueryClientLike,
    bucket_name: str,
    table_id: str,
    date_field: str,
    cluster_field: str,
    objects_by_date: dict[str, list[str]],
) -> BigQueryLoadResult:
    loaded_rows = 0
    for trade_date, object_names in objects_by_date.items():
        partition = trade_date.replace("-", "")
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            time_partitioning=bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field=date_field,
            ),
            clustering_fields=[cluster_field],
        )
        uris = [f"gs://{bucket_name}/{name}" for name in object_names]
        job = bigquery_client.load_table_from_uri(
            uris,
            f"{table_id}${partition}",
            job_config=job_config,
        )
        job.result()
        loaded_rows += job.output_rows or 0

    return BigQueryLoadResult(
        loaded_partition_count=len(objects_by_date),
        loaded_row_count=loaded_rows,
    )


def _replace_table(
    bigquery_client: BigQueryClientLike,
    bucket_name: str,
    table_id: str,
    date_field: str,
    cluster_field: str,
    objects_by_date: dict[str, list[str]],
) -> BigQueryLoadResult:
    object_names = [
        object_name for names in objects_by_date.values() for object_name in names
    ]
    if not object_names:
        return BigQueryLoadResult(0, 0)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=date_field,
        ),
        clustering_fields=[cluster_field],
    )
    uris = [f"gs://{bucket_name}/{name}" for name in object_names]
    job = bigquery_client.load_table_from_uri(
        uris,
        table_id,
        job_config=job_config,
    )
    job.result()
    return BigQueryLoadResult(
        loaded_partition_count=len(objects_by_date),
        loaded_row_count=job.output_rows or 0,
    )


def load_raw_daily_bars(
    bucket_name: str,
    project_id: str,
    dataset_id: str = "stock_analytics",
    *,
    storage_client: StorageClientLike | None = None,
    bigquery_client: BigQueryClientLike | None = None,
) -> BigQueryLoadResult:
    """Load completed J-Quants and Yahoo daily-bar artifacts into BigQuery."""
    gcs = storage_client or cast(StorageClientLike, storage.Client(project=project_id))
    bq = bigquery_client or cast(
        BigQueryClientLike, bigquery.Client(project=project_id)
    )

    jquants_result = _load_partitions(
        bq,
        bucket_name,
        f"{project_id}.{dataset_id}.raw_jquants_equity_daily_bars",
        "Date",
        "Code",
        _completed_parquet_by_partition(gcs, bucket_name, JQUANTS_PREFIX, "trade_date"),
    )
    yahoo_result = _load_partitions(
        bq,
        bucket_name,
        f"{project_id}.{dataset_id}.raw_yahoo_equity_daily_bars",
        "trade_date",
        "yahoo_ticker",
        _completed_parquet_by_partition(
            gcs, bucket_name, YFINANCE_PREFIX, "trade_date"
        ),
    )

    return BigQueryLoadResult(
        loaded_partition_count=(
            jquants_result.loaded_partition_count + yahoo_result.loaded_partition_count
        ),
        loaded_row_count=(
            jquants_result.loaded_row_count + yahoo_result.loaded_row_count
        ),
    )


def load_all_raw_artifacts(
    bucket_name: str,
    project_id: str,
    dataset_id: str = "stock_analytics",
    *,
    storage_client: StorageClientLike | None = None,
    bigquery_client: BigQueryClientLike | None = None,
) -> BigQueryLoadResult:
    """Replace every currently supported raw table for initial bootstrap."""
    gcs = storage_client or cast(StorageClientLike, storage.Client(project=project_id))
    bq = bigquery_client or cast(
        BigQueryClientLike, bigquery.Client(project=project_id)
    )
    table_prefix = f"{project_id}.{dataset_id}"
    results = [
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_jquants_equity_daily_bars",
            "Date",
            "Code",
            _completed_parquet_by_partition(
                gcs, bucket_name, JQUANTS_PREFIX, "trade_date"
            ),
        ),
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_yahoo_equity_daily_bars",
            "trade_date",
            "yahoo_ticker",
            _completed_parquet_by_partition(
                gcs, bucket_name, YFINANCE_PREFIX, "trade_date"
            ),
        ),
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_jquants_equity_master",
            "Date",
            "Code",
            _completed_parquet_by_partition(
                gcs, bucket_name, "jquants/equity_master", "snapshot_date"
            ),
        ),
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_jquants_financial_summary",
            "DiscDate",
            "Code",
            _completed_parquet_by_partition(
                gcs, bucket_name, "jquants/financial_summary", "disclosure_date"
            ),
        ),
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_jquants_earnings_date",
            "PubDate",
            "Code",
            _completed_parquet_by_partition(
                gcs, bucket_name, "jquants/earnings_date", "publication_date"
            ),
        ),
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_jpx_listed_issues",
            "snapshot_date",
            "security_code",
            _completed_parquet_by_partition(
                gcs, bucket_name, "jpx/listed_issues", "snapshot_date"
            ),
        ),
        _replace_table(
            bq,
            bucket_name,
            f"{table_prefix}.raw_yahoo_equity_daily_bars_coverage",
            "start_date",
            "yahoo_ticker",
            _completed_parquet_by_partition(
                gcs,
                bucket_name,
                "yfinance/equity_daily_bars_coverage",
                "start_date",
            ),
        ),
    ]
    return BigQueryLoadResult(
        loaded_partition_count=sum(result.loaded_partition_count for result in results),
        loaded_row_count=sum(result.loaded_row_count for result in results),
    )
