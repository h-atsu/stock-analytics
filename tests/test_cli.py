from pathlib import Path

from typer.testing import CliRunner

from stock_analytics.cli import app
from stock_analytics.ingestion.storage import IngestionArtifact, ListedIssuesArtifact
from stock_analytics.ingestion.yahoo import YahooIngestionResult
from stock_analytics.publishing.gcs import GcsPublishResult

runner = CliRunner()


def test_daily_bars_command(monkeypatch, tmp_path: Path) -> None:
    artifact = IngestionArtifact(
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=42,
    )

    def fake_ingest(trade_date, output_dir):
        assert trade_date.isoformat() == "2024-07-25"
        assert output_dir == tmp_path
        return artifact

    monkeypatch.setattr("stock_analytics.cli.ingest_daily_bars", fake_ingest)

    result = runner.invoke(
        app,
        [
            "ingest",
            "daily-bars",
            "--date",
            "2024-07-25",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "rows=42" in result.stdout
    assert f"parquet={artifact.data_path}" in result.stdout


def test_daily_bars_command_rejects_invalid_date() -> None:
    result = runner.invoke(
        app,
        ["ingest", "daily-bars", "--date", "20240725"],
    )

    assert result.exit_code == 2
    assert "YYYY-MM-DD" in result.output


def test_equity_master_command(monkeypatch, tmp_path: Path) -> None:
    artifact = IngestionArtifact(
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=4378,
    )

    def fake_ingest(snapshot_date, output_dir):
        assert snapshot_date.isoformat() == "2024-07-25"
        assert output_dir == tmp_path
        return artifact

    monkeypatch.setattr("stock_analytics.cli.ingest_equity_master", fake_ingest)

    result = runner.invoke(
        app,
        [
            "ingest",
            "equity-master",
            "--date",
            "2024-07-25",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "rows=4378" in result.stdout
    assert f"parquet={artifact.data_path}" in result.stdout


def test_financial_summary_command(monkeypatch, tmp_path: Path) -> None:
    artifact = IngestionArtifact(
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=43,
    )

    def fake_ingest(disclosure_date, output_dir):
        assert disclosure_date.isoformat() == "2024-07-25"
        assert output_dir == tmp_path
        return artifact

    monkeypatch.setattr("stock_analytics.cli.ingest_financial_summary", fake_ingest)

    result = runner.invoke(
        app,
        [
            "ingest",
            "financial-summary",
            "--date",
            "2024-07-25",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "rows=43" in result.stdout
    assert f"parquet={artifact.data_path}" in result.stdout


def test_earnings_date_command(monkeypatch, tmp_path: Path) -> None:
    artifact = IngestionArtifact(
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=20,
    )

    def fake_ingest(publication_date, output_dir):
        assert publication_date.isoformat() == "2024-07-25"
        assert output_dir == tmp_path
        return artifact

    monkeypatch.setattr("stock_analytics.cli.ingest_earnings_date", fake_ingest)

    result = runner.invoke(
        app,
        [
            "ingest",
            "earnings-date",
            "--date",
            "2024-07-25",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "rows=20" in result.stdout
    assert f"parquet={artifact.data_path}" in result.stdout


def test_listed_issues_command(monkeypatch, tmp_path: Path) -> None:
    artifact = ListedIssuesArtifact(
        source_path=tmp_path / "source.xls",
        data_path=tmp_path / "data.parquet",
        manifest_path=tmp_path / "manifest.json",
        row_count=4444,
    )
    monkeypatch.setattr(
        "stock_analytics.cli.ingest_listed_issues",
        lambda output_dir: artifact,
    )

    result = runner.invoke(
        app,
        ["ingest", "listed-issues", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "rows=4444" in result.stdout
    assert f"source={artifact.source_path}" in result.stdout


def test_listed_issues_command_reports_unchanged(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "stock_analytics.cli.ingest_listed_issues",
        lambda output_dir: None,
    )

    result = runner.invoke(
        app,
        ["ingest", "listed-issues", "--output-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert result.stdout == "unchanged=true\n"


def test_yahoo_daily_bars_command(monkeypatch, tmp_path: Path) -> None:
    coverage = IngestionArtifact(
        data_path=tmp_path / "coverage.parquet",
        manifest_path=tmp_path / "coverage.json",
        row_count=2,
    )
    result_value = YahooIngestionResult(
        data_artifacts=(),
        coverage_artifact=coverage,
        row_count=10,
        available_ticker_count=1,
        no_data_ticker_count=1,
    )
    monkeypatch.setattr(
        "stock_analytics.cli.load_latest_yahoo_tickers",
        lambda listed_issues_dir: ["1301.T", "9999.T"],
    )
    monkeypatch.setattr(
        "stock_analytics.cli.ingest_yahoo_daily_bars",
        lambda tickers, start_date, end_date, output_dir: result_value,
    )

    result = runner.invoke(
        app,
        [
            "ingest",
            "yahoo-daily-bars",
            "--start-date",
            "2026-08-01",
            "--end-date",
            "2026-08-07",
            "--listed-issues-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "rows=10" in result.stdout
    assert "available_tickers=1" in result.stdout
    assert "no_data_tickers=1" in result.stdout


def test_publish_raw_command(monkeypatch, tmp_path: Path) -> None:
    def fake_publish(source_dir: Path, bucket_name: str) -> GcsPublishResult:
        assert source_dir == tmp_path
        assert bucket_name == "raw-bucket"
        return GcsPublishResult(uploaded_count=8, skipped_count=2)

    monkeypatch.setattr("stock_analytics.cli.publish_raw_artifacts", fake_publish)

    result = runner.invoke(
        app,
        [
            "publish",
            "raw",
            "--bucket",
            "raw-bucket",
            "--source-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "uploaded_files=8" in result.stdout
    assert "skipped_files=2" in result.stdout
