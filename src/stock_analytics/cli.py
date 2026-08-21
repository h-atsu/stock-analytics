from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import pandera.pandas as pa
import typer
from dotenv import load_dotenv

from stock_analytics.bootstrap import bootstrap_raw
from stock_analytics.ingestion.jpx import ingest_listed_issues
from stock_analytics.ingestion.jquants import (
    ingest_daily_bars,
    ingest_earnings_date,
    ingest_equity_master,
    ingest_financial_summary,
)
from stock_analytics.ingestion.yahoo import (
    ingest_yahoo_daily_bars,
    load_latest_yahoo_tickers,
)
from stock_analytics.pipeline import DEFAULT_REGION, run_daily_pipeline
from stock_analytics.publishing.bigquery import (
    load_all_raw_artifacts,
    load_raw_daily_bars,
)
from stock_analytics.publishing.gcs import publish_raw_artifacts

app = typer.Typer(no_args_is_help=True, help="Stock analytics data pipeline.")
ingest_app = typer.Typer(no_args_is_help=True, help="Ingest source data.")
publish_app = typer.Typer(no_args_is_help=True, help="Publish validated data.")
load_app = typer.Typer(no_args_is_help=True, help="Load published data.")
bootstrap_app = typer.Typer(no_args_is_help=True, help="Bootstrap initial data.")
pipeline_app = typer.Typer(no_args_is_help=True, help="Run production pipelines.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(publish_app, name="publish")
app.add_typer(load_app, name="load")
app.add_typer(bootstrap_app, name="bootstrap")
app.add_typer(pipeline_app, name="pipeline")


def _parse_iso_date(value: str) -> date:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise typer.BadParameter("YYYY-MM-DD形式で指定してください。")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("YYYY-MM-DD形式で指定してください。") from exc


def _today_in_tokyo() -> date:
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def _json_log(event: str, severity: str = "INFO", **fields: object) -> None:
    typer.echo(
        json.dumps(
            {"event": event, "severity": severity, **fields},
            ensure_ascii=False,
            sort_keys=True,
        ),
        err=severity == "ERROR",
    )


@ingest_app.command("daily-bars")
def daily_bars(
    trade_date: Annotated[
        str,
        typer.Option("--date", help="取得対象の取引日（YYYY-MM-DD）。"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="rawデータの出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/jquants"),
) -> None:
    """J-Quantsの株価日足を検証してParquetへ保存する。"""
    parsed_date = _parse_iso_date(trade_date)
    load_dotenv()

    try:
        artifact = ingest_daily_bars(parsed_date, output_dir)
    except pa.errors.SchemaErrors as exc:
        typer.echo(f"データ検証に失敗しました:\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"取り込みに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if artifact is None:
        typer.echo("no_data=true")
        return

    typer.echo(f"rows={artifact.row_count}")
    typer.echo(f"parquet={artifact.data_path}")
    typer.echo(f"manifest={artifact.manifest_path}")


@ingest_app.command("equity-master")
def equity_master(
    snapshot_date: Annotated[
        str,
        typer.Option("--date", help="取得対象の基準日（YYYY-MM-DD）。"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="rawデータの出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/jquants"),
) -> None:
    """J-Quantsの銘柄マスターを検証してParquetへ保存する。"""
    parsed_date = _parse_iso_date(snapshot_date)
    load_dotenv()

    try:
        artifact = ingest_equity_master(parsed_date, output_dir)
    except pa.errors.SchemaErrors as exc:
        typer.echo(f"データ検証に失敗しました:\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"取り込みに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if artifact is None:
        typer.echo("no_data=true")
        return

    typer.echo(f"rows={artifact.row_count}")
    typer.echo(f"parquet={artifact.data_path}")
    typer.echo(f"manifest={artifact.manifest_path}")


@ingest_app.command("financial-summary")
def financial_summary(
    disclosure_date: Annotated[
        str,
        typer.Option("--date", help="取得対象の開示日（YYYY-MM-DD）。"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="rawデータの出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/jquants"),
) -> None:
    """J-Quantsの財務サマリーを検証してParquetへ保存する。"""
    parsed_date = _parse_iso_date(disclosure_date)
    load_dotenv()

    try:
        artifact = ingest_financial_summary(parsed_date, output_dir)
    except pa.errors.SchemaErrors as exc:
        typer.echo(f"データ検証に失敗しました:\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"取り込みに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if artifact is None:
        typer.echo("no_data=true")
        return

    typer.echo(f"rows={artifact.row_count}")
    typer.echo(f"parquet={artifact.data_path}")
    typer.echo(f"manifest={artifact.manifest_path}")


@ingest_app.command("earnings-date")
def earnings_date(
    publication_date: Annotated[
        str,
        typer.Option("--date", help="取得対象の公表日（YYYY-MM-DD）。"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="rawデータの出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/jquants"),
) -> None:
    """J-Quantsの決算発表予定日を検証してParquetへ保存する。"""
    parsed_date = _parse_iso_date(publication_date)
    load_dotenv()

    try:
        artifact = ingest_earnings_date(parsed_date, output_dir)
    except pa.errors.SchemaErrors as exc:
        typer.echo(f"データ検証に失敗しました:\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"取り込みに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if artifact is None:
        typer.echo("no_data=true")
        return

    typer.echo(f"rows={artifact.row_count}")
    typer.echo(f"parquet={artifact.data_path}")
    typer.echo(f"manifest={artifact.manifest_path}")


@ingest_app.command("listed-issues")
def listed_issues(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="rawデータの出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/jpx"),
) -> None:
    """JPXの現行上場銘柄一覧を検証し、変更時だけ保存する。"""
    try:
        artifact = ingest_listed_issues(output_dir)
    except pa.errors.SchemaErrors as exc:
        typer.echo(f"データ検証に失敗しました:\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"取り込みに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if artifact is None:
        typer.echo("unchanged=true")
        return

    typer.echo(f"rows={artifact.row_count}")
    typer.echo(f"source={artifact.source_path}")
    typer.echo(f"parquet={artifact.data_path}")
    typer.echo(f"manifest={artifact.manifest_path}")


@ingest_app.command("yahoo-daily-bars")
def yahoo_daily_bars(
    start_date: Annotated[
        str,
        typer.Option("--start-date", help="取得開始日（YYYY-MM-DD、包含）。"),
    ],
    end_date: Annotated[
        str,
        typer.Option("--end-date", help="取得終了日（YYYY-MM-DD、包含）。"),
    ],
    listed_issues_dir: Annotated[
        Path,
        typer.Option(
            "--listed-issues-dir",
            help="JPX上場銘柄一覧の出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/jpx"),
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="rawデータの出力ルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw/yfinance"),
) -> None:
    """Yahoo Financeの日足とコーポレートアクションを保存する。"""
    parsed_start = _parse_iso_date(start_date)
    parsed_end = _parse_iso_date(end_date)

    try:
        tickers = load_latest_yahoo_tickers(listed_issues_dir)
        result = ingest_yahoo_daily_bars(
            tickers,
            parsed_start,
            parsed_end,
            output_dir,
        )
    except pa.errors.SchemaErrors as exc:
        typer.echo(f"データ検証に失敗しました:\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"取り込みに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"rows={result.row_count}")
    typer.echo(f"daily_files={len(result.data_artifacts)}")
    typer.echo(f"available_tickers={result.available_ticker_count}")
    typer.echo(f"no_data_tickers={result.no_data_ticker_count}")
    typer.echo(f"coverage={result.coverage_artifact.data_path}")


@publish_app.command("raw")
def publish_raw(
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="publish先のGCS bucket名。"),
    ],
    source_dir: Annotated[
        Path,
        typer.Option(
            "--source-dir",
            help="local rawデータのルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw"),
) -> None:
    """検証済みParquetとmanifestをGCSへpublishする。"""
    try:
        result = publish_raw_artifacts(source_dir, bucket)
    except Exception as exc:
        typer.echo(f"publishに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"uploaded_files={result.uploaded_count}")
    typer.echo(f"skipped_files={result.skipped_count}")


@load_app.command("daily-bars")
def load_daily_bars(
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="raw artifactのGCS bucket名。"),
    ],
    project: Annotated[
        str,
        typer.Option("--project", help="BigQueryのGCP project ID。"),
    ],
    dataset: Annotated[
        str,
        typer.Option("--dataset", help="BigQuery dataset ID。"),
    ] = "stock_analytics",
) -> None:
    """J-QuantsとYahoo Financeの日足をBigQueryへloadする。"""
    try:
        result = load_raw_daily_bars(bucket, project, dataset)
    except Exception as exc:
        typer.echo(f"BigQuery loadに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"loaded_partitions={result.loaded_partition_count}")
    typer.echo(f"loaded_rows={result.loaded_row_count}")


@load_app.command("raw")
def load_raw(
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="raw artifactのGCS bucket名。"),
    ],
    project: Annotated[
        str,
        typer.Option("--project", help="BigQueryのGCP project ID。"),
    ],
    dataset: Annotated[
        str,
        typer.Option("--dataset", help="BigQuery dataset ID。"),
    ] = "stock_analytics",
) -> None:
    """対応済みの全raw artifactをBigQueryへloadする。"""
    try:
        result = load_all_raw_artifacts(bucket, project, dataset)
    except Exception as exc:
        typer.echo(f"BigQuery loadに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"loaded_partitions={result.loaded_partition_count}")
    typer.echo(f"loaded_rows={result.loaded_row_count}")


@bootstrap_app.command("raw")
def run_bootstrap_raw(
    as_of: Annotated[
        str,
        typer.Option("--as-of", help="bootstrap基準日（YYYY-MM-DD）。"),
    ],
    project: Annotated[
        str,
        typer.Option("--project", help="GCP project ID。"),
    ],
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="raw artifactのGCS bucket名。"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="local rawデータのルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw"),
    dataset: Annotated[
        str,
        typer.Option("--dataset", help="BigQuery dataset ID。"),
    ] = "stock_analytics",
    jquants_start_date: Annotated[
        str | None,
        typer.Option(
            "--jquants-start-date",
            help="J-Quants開始日の上書き（小期間の動作確認用）。",
        ),
    ] = None,
    yahoo_start_date: Annotated[
        str | None,
        typer.Option(
            "--yahoo-start-date",
            help="Yahoo開始日の上書き（小期間の動作確認用）。",
        ),
    ] = None,
) -> None:
    """rawデータをlocal取得し、GCSとBigQueryまで初期構築する。"""
    load_dotenv()
    parsed_as_of = _parse_iso_date(as_of)
    parsed_jquants_start = (
        _parse_iso_date(jquants_start_date) if jquants_start_date is not None else None
    )
    parsed_yahoo_start = (
        _parse_iso_date(yahoo_start_date) if yahoo_start_date is not None else None
    )
    try:
        result = bootstrap_raw(
            parsed_as_of,
            project,
            bucket,
            output_dir,
            dataset,
            jquants_start_date=parsed_jquants_start,
            yahoo_start_date=parsed_yahoo_start,
            progress=typer.echo,
        )
    except Exception as exc:
        typer.echo(f"bootstrapに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"fetched_artifacts={result.fetched_artifact_count}")
    typer.echo(f"skipped_partitions={result.skipped_partition_count}")
    typer.echo(f"no_data={result.no_data_count}")
    typer.echo(f"yahoo_rows={result.yahoo_row_count}")
    typer.echo(f"uploaded_files={result.publish_result.uploaded_count}")
    typer.echo(f"loaded_partitions={result.load_result.loaded_partition_count}")
    typer.echo(f"loaded_rows={result.load_result.loaded_row_count}")


@pipeline_app.command("daily")
def run_pipeline_daily(
    project: Annotated[
        str,
        typer.Option("--project", help="GCP project ID。"),
    ],
    bucket: Annotated[
        str,
        typer.Option("--bucket", help="raw artifactのGCS bucket名。"),
    ],
    as_of: Annotated[
        str | None,
        typer.Option(
            "--as-of",
            help="処理基準日（YYYY-MM-DD）。省略時はAsia/Tokyoの当日。",
        ),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="一時的なlocal rawデータのルート。",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("data/raw"),
    dataset: Annotated[
        str,
        typer.Option("--dataset", help="BigQuery dataset ID。"),
    ] = "stock_analytics",
    region: Annotated[
        str,
        typer.Option("--region", help="BigQueryとCloud RunのGCP region。"),
    ] = DEFAULT_REGION,
    structured_logs: Annotated[
        bool,
        typer.Option(
            "--structured-logs/--no-structured-logs",
            help="Cloud Logging向けJSON Linesを出力する。",
        ),
    ] = False,
) -> None:
    """日次データを取得し、GCS・BigQuery・dbtまで直列実行する。"""
    load_dotenv()
    parsed_as_of = _parse_iso_date(as_of) if as_of is not None else _today_in_tokyo()
    started_at = time.monotonic()
    progress = lambda message: (
        _json_log("pipeline_progress", message=message)
        if structured_logs
        else typer.echo(message)
    )
    try:
        result = run_daily_pipeline(
            parsed_as_of,
            project,
            bucket,
            output_dir,
            dataset,
            region,
            progress=progress,
        )
    except Exception as exc:
        if structured_logs:
            _json_log(
                "pipeline_complete",
                severity="ERROR",
                status="error",
                as_of=parsed_as_of.isoformat(),
                duration_seconds=round(time.monotonic() - started_at, 3),
                error_type=type(exc).__name__,
                error=str(exc),
            )
        else:
            typer.echo(f"日次pipelineに失敗しました: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if structured_logs:
        _json_log(
            "pipeline_complete",
            status="success",
            as_of=result.as_of.isoformat(),
            jquants_date=result.jquants_date.isoformat(),
            yahoo_start_date=result.yahoo_start_date.isoformat(),
            yahoo_end_date=result.as_of.isoformat(),
            sources=["jpx", "jquants", "yahoo"],
            fetched_artifacts=result.fetched_artifact_count,
            skipped_artifacts=result.skipped_artifact_count,
            no_data=result.no_data_count,
            yahoo_rows=result.yahoo_row_count,
            yahoo_no_data_tickers=result.yahoo_no_data_ticker_count,
            uploaded_files=result.publish_result.uploaded_count,
            loaded_partitions=result.load_result.loaded_partition_count,
            loaded_rows=result.load_result.loaded_row_count,
            duration_seconds=round(result.duration_seconds, 3),
        )
        return

    typer.echo(f"as_of={result.as_of}")
    typer.echo(f"jquants_date={result.jquants_date}")
    typer.echo(f"yahoo_start_date={result.yahoo_start_date}")
    typer.echo(f"fetched_artifacts={result.fetched_artifact_count}")
    typer.echo(f"skipped_artifacts={result.skipped_artifact_count}")
    typer.echo(f"no_data={result.no_data_count}")
    typer.echo(f"yahoo_rows={result.yahoo_row_count}")
    typer.echo(f"yahoo_no_data_tickers={result.yahoo_no_data_ticker_count}")
    typer.echo(f"duration_seconds={result.duration_seconds:.3f}")
    typer.echo(f"uploaded_files={result.publish_result.uploaded_count}")
    typer.echo(f"loaded_partitions={result.load_result.loaded_partition_count}")
    typer.echo(f"loaded_rows={result.load_result.loaded_row_count}")
