from __future__ import annotations

from datetime import date
from typing import ClassVar

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series


class DailyBars(pa.DataFrameModel):
    """J-Quants `/equities/bars/daily` response contract."""

    Date: Series[pd.Timestamp]
    Code: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{5}$")
    O: Series[float] = pa.Field(nullable=True)
    H: Series[float] = pa.Field(nullable=True)
    L: Series[float] = pa.Field(nullable=True)
    C: Series[float] = pa.Field(nullable=True)
    UL: Series[str] = pa.Field(isin=["0", "1"])
    LL: Series[str] = pa.Field(isin=["0", "1"])
    Vo: Series[float] = pa.Field(ge=0, nullable=True)
    Va: Series[float] = pa.Field(ge=0, nullable=True)
    AdjFactor: Series[float] = pa.Field(gt=0)
    AdjO: Series[float] = pa.Field(nullable=True)
    AdjH: Series[float] = pa.Field(nullable=True)
    AdjL: Series[float] = pa.Field(nullable=True)
    AdjC: Series[float] = pa.Field(nullable=True)
    AdjVo: Series[float] = pa.Field(ge=0, nullable=True)
    MktCap: Series[float] = pa.Field(ge=0, nullable=True)
    ExRT: Series[object] = pa.Field(nullable=True)

    @pa.dataframe_check
    def is_not_empty(cls, frame: pd.DataFrame) -> bool:
        return not frame.empty

    @pa.dataframe_check
    def high_is_not_below_low(cls, frame: pd.DataFrame) -> Series[bool]:
        return frame["H"].isna() | frame["L"].isna() | frame["H"].ge(frame["L"])

    @pa.dataframe_check
    def adjusted_high_is_not_below_low(cls, frame: pd.DataFrame) -> Series[bool]:
        return (
            frame["AdjH"].isna()
            | frame["AdjL"].isna()
            | frame["AdjH"].ge(frame["AdjL"])
        )

    class Config:
        strict = True
        unique: ClassVar[list[str]] = ["Date", "Code"]
        name = "jquants_equity_daily_bars"


def daily_bars_model(trade_date: date) -> type[DailyBars]:
    """Create a daily-bars contract scoped to the requested trade date."""

    class DailyBarsForTradeDate(DailyBars):
        @pa.check("Date")
        def matches_requested_trade_date(
            cls, series: Series[pd.Timestamp]
        ) -> Series[bool]:
            return series.dt.date.eq(trade_date)

    DailyBarsForTradeDate.__name__ = f"DailyBars_{trade_date:%Y%m%d}"
    return DailyBarsForTradeDate


class EquityMaster(pa.DataFrameModel):
    """J-Quants `/equities/master` response contract."""

    Date: Series[pd.Timestamp]
    Code: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{5}$")
    CoName: Series[str]
    CoNameEn: Series[str]
    S17: Series[str]
    S17Nm: Series[str]
    S33: Series[str]
    S33Nm: Series[str]
    ScaleCat: Series[str]
    Mkt: Series[str]
    MktNm: Series[str]
    Mrgn: Series[str]
    MrgnNm: Series[str]

    @pa.dataframe_check
    def is_not_empty(cls, frame: pd.DataFrame) -> bool:
        return not frame.empty

    class Config:
        strict = True
        unique: ClassVar[list[str]] = ["Date", "Code"]
        name = "jquants_equity_master"


def equity_master_model(snapshot_date: date) -> type[EquityMaster]:
    """Create an equity-master contract scoped to the requested date."""

    class EquityMasterForSnapshotDate(EquityMaster):
        @pa.check("Date")
        def matches_requested_snapshot_date(
            cls, series: Series[pd.Timestamp]
        ) -> Series[bool]:
            return series.dt.date.eq(snapshot_date)

    EquityMasterForSnapshotDate.__name__ = f"EquityMaster_{snapshot_date:%Y%m%d}"
    return EquityMasterForSnapshotDate
