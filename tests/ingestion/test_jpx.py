from datetime import UTC, datetime

import pandas as pd

from stock_analytics.ingestion.jpx import (
    LISTED_ISSUES_PAGE_URL,
    find_listed_issues_url,
    ingest_listed_issues,
    normalize_listed_issues,
)
from tests.ingestion.test_schemas import valid_jpx_listed_issues

SOURCE_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/example-att/data_j.xls"
)


def source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "日付": ["20260731", "20260731", "20260731"],
            "コード": ["1301", "1305", "25935"],
            "銘柄名": ["極洋", "iFreeETF TOPIX", "伊藤園第１種優先株式"],
            "市場・商品区分": [
                "プライム（内国株式）",
                "ETF・ETN",
                "プライム（内国株式）",
            ],
            "33業種コード": ["50", "-", "3050"],
            "33業種区分": ["水産・農林業", "-", "食料品"],
            "17業種コード": ["1", "-", "1"],
            "17業種区分": ["食品", "-", "食品"],
            "規模コード": ["6", "-", "-"],
            "規模区分": ["TOPIX Small 1", "-", "-"],
        }
    )


def test_find_listed_issues_url_resolves_official_relative_link() -> None:
    page = b'<a href="example-att/data_j.xls">Excel</a>'

    assert find_listed_issues_url(page) == SOURCE_URL


def test_normalize_listed_issues_preserves_all_instruments(monkeypatch) -> None:
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: source_frame())

    normalized = normalize_listed_issues(b"excel")

    assert normalized["security_code"].tolist() == ["1301", "1305", "25935"]
    assert normalized["sector_33_code"].tolist() == ["0050", pd.NA, "3050"]
    assert normalized["yahoo_ticker"].tolist() == ["1301.T", "1305.T", pd.NA]


def test_ingest_listed_issues_downloads_validates_and_stores(
    monkeypatch, tmp_path
) -> None:
    page = b'<a href="example-att/data_j.xls">Excel</a>'
    requested_urls: list[str] = []

    def fake_get(url: str) -> bytes:
        requested_urls.append(url)
        return page if url == LISTED_ISSUES_PAGE_URL else b"excel"

    monkeypatch.setattr(
        "stock_analytics.ingestion.jpx.normalize_listed_issues",
        lambda content: valid_jpx_listed_issues(),
    )

    artifact = ingest_listed_issues(
        tmp_path,
        http_get=fake_get,
        ingested_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )

    assert requested_urls == [LISTED_ISSUES_PAGE_URL, SOURCE_URL]
    assert artifact is not None
    assert artifact.row_count == 2
    assert artifact.source_path.read_bytes() == b"excel"
