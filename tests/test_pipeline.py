from datetime import date
from pathlib import Path
from typing import cast

from stock_analytics.ingestion.storage import IngestionArtifact
from stock_analytics.ingestion.yahoo import YahooIngestionResult
from stock_analytics.pipeline import DailyPipelineJQuantsClient, run_daily_pipeline
from stock_analytics.publishing.bigquery import BigQueryLoadResult
from stock_analytics.publishing.gcs import GcsPublishResult


def test_run_daily_pipeline_runs_fixed_date_end_to_end(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = IngestionArtifact(
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=1,
    )
    requested: list[date] = []
    messages: list[str] = []
    dbt_calls: list[tuple[str, str, str, Path]] = []

    monkeypatch.setattr(
        "stock_analytics.pipeline.sync_latest_listed_issues_artifact",
        lambda bucket, root: True,
    )
    monkeypatch.setattr(
        "stock_analytics.pipeline.ingest_listed_issues", lambda root: None
    )
    monkeypatch.setattr(
        "stock_analytics.pipeline._request_jquants",
        lambda request, progress, sleep: request(),
    )

    def fetched(target_date, root, *, client):
        del root, client
        requested.append(target_date)
        return artifact

    def no_data(target_date, root, *, client):
        del root, client
        requested.append(target_date)

    monkeypatch.setattr("stock_analytics.pipeline.ingest_daily_bars", fetched)
    monkeypatch.setattr("stock_analytics.pipeline.ingest_financial_summary", no_data)
    monkeypatch.setattr("stock_analytics.pipeline.ingest_earnings_date", fetched)
    monkeypatch.setattr(
        "stock_analytics.pipeline.load_latest_yahoo_tickers",
        lambda root: ["7203.T"],
    )

    def yahoo(tickers, start_date, end_date, root):
        assert tickers == ["7203.T"]
        assert start_date == date(2026, 8, 14)
        assert end_date == date(2026, 8, 21)
        assert root == tmp_path / "yfinance"
        return YahooIngestionResult(
            data_artifacts=(artifact, artifact),
            coverage_artifact=artifact,
            row_count=20,
            available_ticker_count=1,
            no_data_ticker_count=0,
        )

    monkeypatch.setattr("stock_analytics.pipeline.ingest_yahoo_daily_bars", yahoo)
    monkeypatch.setattr(
        "stock_analytics.pipeline.publish_raw_artifacts",
        lambda root, bucket: GcsPublishResult(10, 2),
    )

    def load(bucket, project, jquants_date, yahoo_start, yahoo_end, dataset):
        assert (jquants_date, yahoo_start, yahoo_end) == (
            date(2026, 5, 29),
            date(2026, 8, 14),
            date(2026, 8, 21),
        )
        return BigQueryLoadResult(7, 100)

    monkeypatch.setattr("stock_analytics.pipeline.load_daily_pipeline_artifacts", load)
    monkeypatch.setattr(
        "stock_analytics.pipeline.run_dbt_build",
        lambda project, dataset, region, project_dir: dbt_calls.append(
            (project, dataset, region, project_dir)
        ),
    )

    result = run_daily_pipeline(
        date(2026, 8, 21),
        "test-project",
        "raw-bucket",
        tmp_path,
        jquants_client=cast(DailyPipelineJQuantsClient, object()),
        progress=messages.append,
        sleep=lambda seconds: None,
        clock=iter((100.0, 112.5)).__next__,
    )

    assert requested == [date(2026, 5, 29)] * 3
    assert result.fetched_artifact_count == 5
    assert result.skipped_artifact_count == 1
    assert result.no_data_count == 1
    assert result.yahoo_row_count == 20
    assert result.duration_seconds == 12.5
    assert result.load_result.loaded_partition_count == 7
    assert dbt_calls == [
        ("test-project", "stock_analytics", "asia-northeast1", Path("dbt"))
    ]
    assert messages[-1] == "dbt buildを実行します"
