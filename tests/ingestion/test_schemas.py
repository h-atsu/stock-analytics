from datetime import date

import pandas as pd
import pandera.pandas as pa
import pytest
from jquantsapi.constants import FIN_SUMMARY_COLUMNS_V2

from stock_analytics.ingestion.schemas import (
    JpxListedIssues,
    daily_bars_model,
    earnings_date_model,
    equity_master_model,
    financial_summary_model,
)


def valid_daily_bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-07-25", "2024-07-25"]),
            "Code": ["13010", "13020"],
            "O": [100.0, None],
            "H": [110.0, None],
            "L": [95.0, None],
            "C": [105.0, None],
            "UL": ["0", "0"],
            "LL": ["0", "0"],
            "Vo": [1000.0, None],
            "Va": [102000.0, None],
            "AdjFactor": [1.0, 1.0],
            "AdjO": [100.0, None],
            "AdjH": [110.0, None],
            "AdjL": [95.0, None],
            "AdjC": [105.0, None],
            "AdjVo": [1000.0, None],
            "MktCap": [1_000_000.0, None],
            "ExRT": [None, None],
        }
    )


def valid_equity_master() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-07-25", "2024-07-25"]),
            "Code": ["13010", "130A0"],
            "CoName": ["極洋", "テスト株式会社"],
            "CoNameEn": ["KYOKUYO CO.,LTD.", "TEST CO.,LTD."],
            "S17": ["1", "10"],
            "S17Nm": ["食品", "情報通信・サービスその他"],
            "S33": ["0050", "5250"],
            "S33Nm": ["水産・農林業", "情報・通信業"],
            "ScaleCat": ["TOPIX Small 1", "-"],
            "Mkt": ["0111", "0113"],
            "MktNm": ["プライム", "グロース"],
            "Mrgn": ["1", "2"],
            "MrgnNm": ["信用", "貸借"],
        }
    )


def valid_financial_summary() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            column: pd.Series([None, None], dtype=object)
            for column in FIN_SUMMARY_COLUMNS_V2
        }
    )
    frame["DiscDate"] = pd.to_datetime(["2024-07-25", "2024-07-25"])
    frame["DiscTime"] = ["15:00", "15:30"]
    frame["Code"] = ["13010", "130A0"]
    frame["DiscNo"] = ["20240725555555", "20240725666666"]
    frame["DocType"] = [
        "FYFinancialStatements_Consolidated_JP",
        "1QFinancialStatements_Consolidated_JP",
    ]
    frame["CurPerType"] = ["FY", "1Q"]
    frame["CurPerSt"] = pd.to_datetime(["2023-04-01", "2024-04-01"])
    frame["CurPerEn"] = pd.to_datetime(["2024-03-31", "2024-06-30"])
    frame["CurFYSt"] = pd.to_datetime(["2023-04-01", "2024-04-01"])
    frame["CurFYEn"] = pd.to_datetime(["2024-03-31", "2025-03-31"])
    frame["NxtFYSt"] = pd.to_datetime([None, "2025-04-01"])
    frame["NxtFYEn"] = pd.to_datetime([None, "2026-03-31"])
    frame["Sales"] = [1_000_000, None]
    return frame


def valid_earnings_date() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PubDate": pd.to_datetime(["2024-07-25", "2024-07-25"]),
            "SchDate": pd.to_datetime(["2024-08-09", None]),
            "FQName": ["FY", "1Q"],
            "FYE": ["2024-06-30", "2025-03-31"],
            "Code": ["13010", "130A0"],
            "CoName": ["極洋", "テスト株式会社"],
            "CoNameEn": ["KYOKUYO CO.,LTD.", "TEST CO.,LTD."],
        }
    )


def valid_jpx_listed_issues() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "snapshot_date": pd.to_datetime(["2026-07-31", "2026-07-31"]),
            "security_code": ["1301", "25935"],
            "security_name": ["極洋", "伊藤園第１種優先株式"],
            "market_product_category": [
                "プライム（内国株式）",
                "プライム（内国株式）",
            ],
            "sector_33_code": ["0050", "3050"],
            "sector_33_name": ["水産・農林業", "食料品"],
            "sector_17_code": ["1", "1"],
            "sector_17_name": ["食品", "食品"],
            "scale_code": ["6", None],
            "scale_category": ["TOPIX Small 1", None],
            "yahoo_ticker": ["1301.T", pd.NA],
        }
    )


def test_daily_bars_model_accepts_nullable_no_trade_row() -> None:
    validated = daily_bars_model(date(2024, 7, 25)).validate(
        valid_daily_bars(), lazy=True
    )

    assert len(validated) == 2


def test_daily_bars_model_factory_scopes_schema_to_trade_date() -> None:
    model = daily_bars_model(date(2024, 7, 25))

    assert model.__name__ == "DailyBars_20240725"
    assert len(model.validate(valid_daily_bars())) == 2


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda frame: frame.assign(Date=pd.Timestamp("2024-07-24")),
            "matches_requested_trade_date",
        ),
        (lambda frame: frame.assign(Vo=-1.0), "greater_than_or_equal_to"),
        (lambda frame: frame.assign(H=90.0, L=95.0), "high_is_not_below_low"),
    ],
)
def test_daily_bars_model_rejects_invalid_rows(mutate, expected: str) -> None:
    with pytest.raises(pa.errors.SchemaErrors, match=expected):
        daily_bars_model(date(2024, 7, 25)).validate(
            mutate(valid_daily_bars()), lazy=True
        )


def test_daily_bars_model_rejects_duplicate_date_and_code() -> None:
    frame = valid_daily_bars().iloc[[0, 0]].reset_index(drop=True)

    with pytest.raises(pa.errors.SchemaErrors, match="multiple_fields_uniqueness"):
        daily_bars_model(date(2024, 7, 25)).validate(frame, lazy=True)


def test_daily_bars_model_rejects_unknown_column() -> None:
    frame = valid_daily_bars().assign(Unexpected="value")

    with pytest.raises(pa.errors.SchemaErrors, match="Unexpected"):
        daily_bars_model(date(2024, 7, 25)).validate(frame, lazy=True)


def test_equity_master_model_accepts_alphanumeric_code() -> None:
    validated = equity_master_model(date(2024, 7, 25)).validate(
        valid_equity_master(), lazy=True
    )

    assert validated["Code"].tolist() == ["13010", "130A0"]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda frame: frame.assign(Date=pd.Timestamp("2024-07-24")),
            "matches_requested_snapshot_date",
        ),
        (lambda frame: frame.assign(Code="1301"), "str_matches"),
    ],
)
def test_equity_master_model_rejects_invalid_rows(mutate, expected: str) -> None:
    with pytest.raises(pa.errors.SchemaErrors, match=expected):
        equity_master_model(date(2024, 7, 25)).validate(
            mutate(valid_equity_master()), lazy=True
        )


def test_equity_master_model_rejects_duplicate_date_and_code() -> None:
    frame = valid_equity_master().iloc[[0, 0]].reset_index(drop=True)

    with pytest.raises(pa.errors.SchemaErrors, match="multiple_fields_uniqueness"):
        equity_master_model(date(2024, 7, 25)).validate(frame, lazy=True)


def test_financial_summary_model_accepts_nullable_financial_values() -> None:
    validated = financial_summary_model(date(2024, 7, 25)).validate(
        valid_financial_summary(), lazy=True
    )

    assert len(validated) == 2
    assert validated["Sales"].iloc[0] == 1_000_000
    assert pd.isna(validated["Sales"].iloc[1])


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda frame: frame.assign(DiscDate=pd.Timestamp("2024-07-24")),
            "matches_requested_disclosure_date",
        ),
        (
            lambda frame: frame.drop(columns="Sales"),
            "has_all_source_columns",
        ),
    ],
)
def test_financial_summary_model_rejects_invalid_data(mutate, expected: str) -> None:
    with pytest.raises(pa.errors.SchemaErrors, match=expected):
        financial_summary_model(date(2024, 7, 25)).validate(
            mutate(valid_financial_summary()), lazy=True
        )


def test_financial_summary_model_rejects_duplicate_disclosure() -> None:
    frame = valid_financial_summary().iloc[[0, 0]].reset_index(drop=True)

    with pytest.raises(pa.errors.SchemaErrors, match="multiple_fields_uniqueness"):
        financial_summary_model(date(2024, 7, 25)).validate(frame, lazy=True)


def test_earnings_date_model_accepts_undecided_schedule() -> None:
    validated = earnings_date_model(date(2024, 7, 25)).validate(
        valid_earnings_date(), lazy=True
    )

    assert len(validated) == 2
    assert pd.isna(validated["SchDate"].iloc[1])


def test_earnings_date_model_rejects_other_publication_date() -> None:
    frame = valid_earnings_date().assign(PubDate=pd.Timestamp("2024-07-24"))

    with pytest.raises(
        pa.errors.SchemaErrors, match="matches_requested_publication_date"
    ):
        earnings_date_model(date(2024, 7, 25)).validate(frame, lazy=True)


def test_earnings_date_model_rejects_duplicate_event() -> None:
    frame = valid_earnings_date().iloc[[0, 0]].reset_index(drop=True)

    with pytest.raises(pa.errors.SchemaErrors, match="multiple_fields_uniqueness"):
        earnings_date_model(date(2024, 7, 25)).validate(frame, lazy=True)


def test_jpx_listed_issues_accepts_standard_and_class_share_codes() -> None:
    validated = JpxListedIssues.validate(valid_jpx_listed_issues(), lazy=True)

    assert validated["yahoo_ticker"].iloc[0] == "1301.T"
    assert pd.isna(validated["yahoo_ticker"].iloc[1])


def test_jpx_listed_issues_rejects_incorrect_yahoo_ticker() -> None:
    frame = valid_jpx_listed_issues()
    frame.loc[1, "yahoo_ticker"] = "2593.T"

    with pytest.raises(
        pa.errors.SchemaErrors, match="yahoo_ticker_matches_security_code"
    ):
        JpxListedIssues.validate(frame, lazy=True)


def test_jpx_listed_issues_rejects_multiple_snapshot_dates() -> None:
    frame = valid_jpx_listed_issues()
    frame.loc[1, "snapshot_date"] = pd.Timestamp("2026-06-30")

    with pytest.raises(pa.errors.SchemaErrors, match="has_one_snapshot_date"):
        JpxListedIssues.validate(frame, lazy=True)
