# %%
import polars as pl

# %%
df = pl.read_parquet(
    "../data/raw/jquants/earnings_date/publication_date=2024-07-25/ingested_at=20260815T143649.670109Z/data.parquet"
)

# %%
