from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated

import pandera.pandas as pa
import typer
from dotenv import load_dotenv

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

app = typer.Typer(no_args_is_help=True, help="Stock analytics data pipeline.")
ingest_app = typer.Typer(no_args_is_help=True, help="Ingest source data.")
app.add_typer(ingest_app, name="ingest")


def _parse_iso_date(value: str) -> date:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise typer.BadParameter("YYYY-MM-DD形式で指定してください。")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("YYYY-MM-DD形式で指定してください。") from exc


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
