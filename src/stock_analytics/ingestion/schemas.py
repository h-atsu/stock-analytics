from __future__ import annotations

from datetime import date
from typing import ClassVar

import pandas as pd
import pandera.pandas as pa
from jquantsapi.constants import FIN_SUMMARY_COLUMNS_V2
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


class FinancialSummary(pa.DataFrameModel):
    """J-Quants `/fins/summary` response contract."""

    DiscDate: Series[pd.Timestamp]
    DiscTime: Series[str]
    Code: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{5}$")
    DiscNo: Series[str]
    DocType: Series[str]
    CurPerType: Series[str]
    CurPerSt: Series[pd.Timestamp]
    CurPerEn: Series[pd.Timestamp]
    CurFYSt: Series[pd.Timestamp]
    CurFYEn: Series[pd.Timestamp]
    NxtFYSt: Series[pd.Timestamp] = pa.Field(nullable=True)
    NxtFYEn: Series[pd.Timestamp] = pa.Field(nullable=True)

    @pa.dataframe_check
    def is_not_empty(cls, frame: pd.DataFrame) -> bool:
        return not frame.empty

    @pa.dataframe_check
    def has_all_source_columns(cls, frame: pd.DataFrame) -> bool:
        return set(FIN_SUMMARY_COLUMNS_V2).issubset(frame.columns)

    class Config:
        strict = False
        unique: ClassVar[list[str]] = ["DiscDate", "Code", "DiscNo"]
        name = "jquants_financial_summary"


def financial_summary_model(disclosure_date: date) -> type[FinancialSummary]:
    """Create a financial-summary contract scoped to the disclosure date."""

    class FinancialSummaryForDisclosureDate(FinancialSummary):
        @pa.check("DiscDate")
        def matches_requested_disclosure_date(
            cls, series: Series[pd.Timestamp]
        ) -> Series[bool]:
            return series.dt.date.eq(disclosure_date)

    FinancialSummaryForDisclosureDate.__name__ = (
        f"FinancialSummary_{disclosure_date:%Y%m%d}"
    )
    return FinancialSummaryForDisclosureDate


class EarningsDate(pa.DataFrameModel):
    """J-Quants `/fins/earnings-date` response contract."""

    PubDate: Series[pd.Timestamp]
    SchDate: Series[pd.Timestamp] = pa.Field(nullable=True)
    FQName: Series[str]
    FYE: Series[str]
    Code: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{5}$")
    CoName: Series[str]
    CoNameEn: Series[str]

    @pa.dataframe_check
    def is_not_empty(cls, frame: pd.DataFrame) -> bool:
        return not frame.empty

    class Config:
        strict = True
        unique: ClassVar[list[str]] = ["PubDate", "Code", "FQName"]
        name = "jquants_earnings_date"


def earnings_date_model(publication_date: date) -> type[EarningsDate]:
    """Create an earnings-date contract scoped to the publication date."""

    class EarningsDateForPublicationDate(EarningsDate):
        @pa.check("PubDate")
        def matches_requested_publication_date(
            cls, series: Series[pd.Timestamp]
        ) -> Series[bool]:
            return series.dt.date.eq(publication_date)

    EarningsDateForPublicationDate.__name__ = f"EarningsDate_{publication_date:%Y%m%d}"
    return EarningsDateForPublicationDate


class JpxListedIssues(pa.DataFrameModel):
    """Normalized JPX listed-issues spreadsheet contract."""

    snapshot_date: Series[pd.Timestamp]
    security_code: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{4,5}$")
    security_name: Series[str]
    market_product_category: Series[str]
    sector_33_code: Series[str] = pa.Field(nullable=True, str_matches=r"^[0-9]{4}$")
    sector_33_name: Series[str] = pa.Field(nullable=True)
    sector_17_code: Series[str] = pa.Field(nullable=True, str_matches=r"^[0-9]{1,2}$")
    sector_17_name: Series[str] = pa.Field(nullable=True)
    scale_code: Series[str] = pa.Field(nullable=True, str_matches=r"^[0-9]+$")
    scale_category: Series[str] = pa.Field(nullable=True)
    yahoo_ticker: Series[str] = pa.Field(nullable=True, str_matches=r"^[0-9A-Z]{4}\.T$")

    @pa.dataframe_check
    def is_not_empty(cls, frame: pd.DataFrame) -> bool:
        return not frame.empty

    @pa.dataframe_check
    def has_one_snapshot_date(cls, frame: pd.DataFrame) -> bool:
        return frame["snapshot_date"].nunique() == 1

    @pa.dataframe_check
    def yahoo_ticker_matches_security_code(cls, frame: pd.DataFrame) -> Series[bool]:
        is_standard_code = frame["security_code"].str.len().eq(4)
        ticker = frame["yahoo_ticker"].fillna("")
        return (is_standard_code & ticker.eq(frame["security_code"] + ".T")) | (
            ~is_standard_code & ticker.eq("")
        )

    class Config:
        strict = True
        unique = "security_code"
        name = "jpx_listed_issues"


class YahooDailyBars(pa.DataFrameModel):
    """Normalized yfinance daily-bars response contract."""

    trade_date: Series[pd.Timestamp]
    yahoo_ticker: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{4}\.T$")
    open: Series[float] = pa.Field(nullable=True)
    high: Series[float] = pa.Field(nullable=True)
    low: Series[float] = pa.Field(nullable=True)
    close: Series[float] = pa.Field(nullable=True)
    adj_close: Series[float] = pa.Field(nullable=True)
    volume: Series[float] = pa.Field(ge=0, nullable=True)
    dividends: Series[float] = pa.Field(ge=0, nullable=True)
    stock_splits: Series[float] = pa.Field(ge=0, nullable=True)
    capital_gains: Series[float] = pa.Field(nullable=True)

    @pa.dataframe_check
    def is_not_empty(cls, frame: pd.DataFrame) -> bool:
        return not frame.empty

    @pa.dataframe_check
    def high_is_not_below_low(cls, frame: pd.DataFrame) -> Series[bool]:
        return (
            frame["high"].isna() | frame["low"].isna() | frame["high"].ge(frame["low"])
        )

    class Config:
        strict = True
        unique: ClassVar[list[str]] = ["trade_date", "yahoo_ticker"]
        name = "yahoo_daily_bars"


def yahoo_daily_bars_model(trade_date: date) -> type[YahooDailyBars]:
    """Create a Yahoo daily-bars contract scoped to one trade date."""

    class YahooDailyBarsForTradeDate(YahooDailyBars):
        @pa.check("trade_date")
        def matches_requested_trade_date(
            cls, series: Series[pd.Timestamp]
        ) -> Series[bool]:
            return series.dt.date.eq(trade_date)

    YahooDailyBarsForTradeDate.__name__ = f"YahooDailyBars_{trade_date:%Y%m%d}"
    return YahooDailyBarsForTradeDate


class YahooCoverage(pa.DataFrameModel):
    """Ticker coverage for one yfinance ingestion run."""

    yahoo_ticker: Series[str] = pa.Field(str_matches=r"^[0-9A-Z]{4}\.T$")
    status: Series[str] = pa.Field(isin=["available", "no_data"])
    row_count: Series[int] = pa.Field(ge=0)
    start_date: Series[pd.Timestamp]
    end_date: Series[pd.Timestamp]

    @pa.dataframe_check
    def status_matches_row_count(cls, frame: pd.DataFrame) -> Series[bool]:
        return frame["status"].eq("available").eq(frame["row_count"].gt(0))

    class Config:
        strict = True
        unique = "yahoo_ticker"
        name = "yahoo_coverage"
