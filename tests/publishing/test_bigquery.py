from dataclasses import dataclass

from google.cloud import bigquery

from stock_analytics.publishing.bigquery import load_raw_daily_bars


@dataclass(frozen=True)
class FakeBlob:
    name: str


class FakeStorageClient:
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def list_blobs(self, bucket_name: str, *, prefix: str) -> list[FakeBlob]:
        del bucket_name
        return [FakeBlob(name) for name in self.names if name.startswith(prefix)]


class FakeJob:
    output_rows = 10

    def result(self) -> None:
        return None


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.loads: list[tuple[list[str], str, bigquery.LoadJobConfig]] = []

    def load_table_from_uri(
        self,
        uris: list[str],
        destination: str,
        *,
        job_config: bigquery.LoadJobConfig,
    ) -> FakeJob:
        self.loads.append((uris, destination, job_config))
        return FakeJob()


def test_load_raw_daily_bars_replaces_completed_date_partitions() -> None:
    storage_client = FakeStorageClient(
        [
            "jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260815T000000Z/data.parquet",
            "jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260815T000000Z/manifest.json",
            "jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260816T000000Z/data.parquet",
            "jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260816T000000Z/manifest.json",
            "yfinance/equity_daily_bars/trade_date=2026-08-15/ingested_at=20260816T000000Z/data.parquet",
            "yfinance/equity_daily_bars/trade_date=2026-08-15/ingested_at=20260816T000000Z/manifest.json",
        ]
    )
    bigquery_client = FakeBigQueryClient()

    result = load_raw_daily_bars(
        "raw-bucket",
        "test-project",
        storage_client=storage_client,
        bigquery_client=bigquery_client,
    )

    assert result.loaded_partition_count == 2
    assert result.loaded_row_count == 20
    assert len(bigquery_client.loads) == 2

    jquants_uris, jquants_destination, jquants_config = bigquery_client.loads[0]
    assert jquants_uris == [
        "gs://raw-bucket/jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260815T000000Z/data.parquet",
        "gs://raw-bucket/jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260816T000000Z/data.parquet",
    ]
    assert jquants_destination == (
        "test-project.stock_analytics.raw_jquants_equity_daily_bars$20260814"
    )
    assert jquants_config.write_disposition == "WRITE_TRUNCATE"
    assert jquants_config.time_partitioning.field == "Date"
    assert jquants_config.clustering_fields == ["Code"]

    _, yahoo_destination, yahoo_config = bigquery_client.loads[1]
    assert yahoo_destination == (
        "test-project.stock_analytics.raw_yahoo_equity_daily_bars$20260815"
    )
    assert yahoo_config.time_partitioning.field == "trade_date"
    assert yahoo_config.clustering_fields == ["yahoo_ticker"]


def test_load_raw_daily_bars_ignores_parquet_without_manifest() -> None:
    storage_client = FakeStorageClient(
        [
            "jquants/equity_daily_bars/trade_date=2026-08-14/ingested_at=20260815T000000Z/data.parquet"
        ]
    )
    bigquery_client = FakeBigQueryClient()

    result = load_raw_daily_bars(
        "raw-bucket",
        "test-project",
        storage_client=storage_client,
        bigquery_client=bigquery_client,
    )

    assert result.loaded_partition_count == 0
    assert result.loaded_row_count == 0
    assert bigquery_client.loads == []
