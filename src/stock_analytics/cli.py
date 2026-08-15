from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated

import pandera.pandas as pa
import typer
from dotenv import load_dotenv

from stock_analytics.ingestion.jquants import ingest_daily_bars

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
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)

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
