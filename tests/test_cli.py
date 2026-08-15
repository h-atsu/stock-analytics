from pathlib import Path

from typer.testing import CliRunner

from stock_analytics.cli import app
from stock_analytics.ingestion.storage import IngestionArtifact

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
