from datetime import date

import pandas as pd
import pandera.pandas as pa
import pytest

from stock_analytics.ingestion.schemas import daily_bars_model, equity_master_model


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
