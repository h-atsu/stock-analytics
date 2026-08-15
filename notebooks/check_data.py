# %%
import polars as pl

# %%
df = pl.read_parquet(
    "../data/raw/jquants/earnings_date/publication_date=2024-07-25/ingested_at=20260815T143649.670109Z/data.parquet"
)

# %%
df = pl.read_parquet(
    "../data/raw/jpx/listed_issues/snapshot_date=2026-07-31/ingested_at=20260815T145355.504115Z/data.parquet"
)
# %%
df = pl.read_parquet(
    "../data/raw/yfinance/equity_daily_bars/trade_date=2024-07-25/ingested_at=20260815T153048.183511Z/data.parquet"
)

# %%
df = pl.read_parquet(
    "../data/raw/yfinance/equity_daily_bars_coverage/start_date=2024-07-25/end_date=2024-07-25/ingested_at=20260815T153048.183511Z/data.parquet"
)
# %%
