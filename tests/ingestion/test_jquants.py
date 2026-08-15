from datetime import UTC, date, datetime

import pandas as pd

from stock_analytics.ingestion.jquants import ingest_daily_bars
from tests.ingestion.test_schemas import valid_daily_bars


class FakeDailyBarsClient:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.requested_date = ""

    def get_eq_bars_daily(
        self,
        code: str = "",
        from_yyyymmdd: str = "",
        to_yyyymmdd: str = "",
        date_yyyymmdd: str = "",
    ) -> pd.DataFrame:
        self.requested_date = date_yyyymmdd
        return self.frame.copy()


def test_ingest_daily_bars_fetches_validates_and_stores(tmp_path) -> None:
    client = FakeDailyBarsClient(valid_daily_bars())

    artifact = ingest_daily_bars(
        date(2024, 7, 25),
        tmp_path,
        client=client,
        ingested_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )

    assert client.requested_date == "20240725"
    assert artifact.row_count == 2
    assert artifact.data_path.is_file()
    assert artifact.manifest_path.is_file()
