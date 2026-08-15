from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import pandas as pd

from stock_analytics.ingestion.schemas import JpxListedIssues
from stock_analytics.ingestion.storage import (
    ListedIssuesArtifact,
    store_jpx_listed_issues,
)

LISTED_ISSUES_PAGE_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
)
SOURCE_COLUMNS = {
    "日付": "snapshot_date",
    "コード": "security_code",
    "銘柄名": "security_name",
    "市場・商品区分": "market_product_category",
    "33業種コード": "sector_33_code",
    "33業種区分": "sector_33_name",
    "17業種コード": "sector_17_code",
    "17業種区分": "sector_17_name",
    "規模コード": "scale_code",
    "規模区分": "scale_category",
}
NULLABLE_COLUMNS = [
    "sector_33_code",
    "sector_33_name",
    "sector_17_code",
    "sector_17_name",
    "scale_code",
    "scale_category",
]

HttpGet = Callable[[str], bytes]


class _ListedIssuesLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value is not None and value.endswith("data_j.xls"):
                self.hrefs.append(value)


def _http_get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "stock-analytics/0.1"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def find_listed_issues_url(page_content: bytes) -> str:
    parser = _ListedIssuesLinkParser()
    parser.feed(page_content.decode("utf-8"))
    if len(parser.hrefs) != 1:
        raise ValueError("JPX上場銘柄一覧のExcelリンクを一意に特定できませんでした")

    source_url = urljoin(LISTED_ISSUES_PAGE_URL, parser.hrefs[0])
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.netloc != "www.jpx.co.jp":
        raise ValueError("JPX以外のExcelリンクは取得しません")
    return source_url


def normalize_listed_issues(source_content: bytes) -> pd.DataFrame:
    frame = pd.read_excel(BytesIO(source_content), engine="xlrd", dtype=str)
    if set(frame.columns) != set(SOURCE_COLUMNS):
        raise ValueError("JPX上場銘柄一覧の列構成が変更されています")

    frame = frame.rename(columns=SOURCE_COLUMNS)[list(SOURCE_COLUMNS.values())]
    for column in frame.columns:
        frame[column] = frame[column].str.strip()

    frame["snapshot_date"] = pd.to_datetime(
        frame["snapshot_date"], format="%Y%m%d", errors="raise"
    )
    frame[NULLABLE_COLUMNS] = frame[NULLABLE_COLUMNS].replace("-", pd.NA)
    frame["sector_33_code"] = frame["sector_33_code"].map(
        lambda value: value.zfill(4) if pd.notna(value) else pd.NA
    )
    frame["yahoo_ticker"] = frame["security_code"].map(
        lambda code: f"{code}.T" if len(code) == 4 else pd.NA
    )
    return frame


def ingest_listed_issues(
    output_root: Path,
    *,
    http_get: HttpGet | None = None,
    ingested_at: datetime | None = None,
) -> ListedIssuesArtifact | None:
    get = http_get or _http_get
    page_content = get(LISTED_ISSUES_PAGE_URL)
    source_url = find_listed_issues_url(page_content)
    source_content = get(source_url)
    frame = normalize_listed_issues(source_content)
    validated = JpxListedIssues.validate(frame, lazy=True)
    return store_jpx_listed_issues(
        validated,
        source_content,
        source_url,
        output_root,
        ingested_at=ingested_at,
    )
