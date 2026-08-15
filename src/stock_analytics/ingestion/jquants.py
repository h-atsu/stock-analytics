from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Protocol

import jquantsapi
import pandas as pd

from stock_analytics.ingestion.schemas import daily_bars_model
from stock_analytics.ingestion.storage import IngestionArtifact, store_daily_bars


class DailyBarsClient(Protocol):
    def get_eq_bars_daily(
        self,
        code: str = "",
        from_yyyymmdd: str = "",
        to_yyyymmdd: str = "",
        date_yyyymmdd: str = "",
    ) -> pd.DataFrame: ...


def fetch_daily_bars(
    trade_date: date,
    client: DailyBarsClient | None = None,
) -> pd.DataFrame:
    api_client = client or jquantsapi.ClientV2()
    return api_client.get_eq_bars_daily(date_yyyymmdd=trade_date.strftime("%Y%m%d"))


def ingest_daily_bars(
    trade_date: date,
    output_root: Path,
    *,
    client: DailyBarsClient | None = None,
    ingested_at: datetime | None = None,
) -> IngestionArtifact:
    frame = fetch_daily_bars(trade_date, client)
    validated = daily_bars_model(trade_date).validate(frame, lazy=True)
    return store_daily_bars(
        validated,
        trade_date,
        output_root,
        ingested_at=ingested_at,
    )
