# %%
import polars as pl

# %%
df = pl.read_parquet(
    "../data/raw/jquants/financial_summary/disclosure_date=2025-07-25/ingested_at=20260815T140157.380738Z/data.parquet"
)

# %%
