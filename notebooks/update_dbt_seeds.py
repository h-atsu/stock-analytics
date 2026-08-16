# %%
import csv
from pathlib import Path

from dotenv import load_dotenv
from IPython.display import display
from jquantsapi import ClientV2

# %%
load_dotenv()
client = ClientV2()

# %%
df_sector_17 = client.get_17_sectors()
display(df_sector_17)

# %%
df_sector_33 = client.get_33_sectors()
display(df_sector_33)

# %%
df_market_segments = client.get_market_segments()
display(df_market_segments)

# %%
assert len(df_sector_17) == 18
assert len(df_sector_33) == 34
assert len(df_market_segments) == 10
assert df_sector_17["S17"].is_unique
assert df_sector_33["S33"].is_unique
assert df_market_segments["Mkt"].is_unique
assert set(df_sector_33["S17"]) <= set(df_sector_17["S17"])

# %%
seed_dir = Path("../dbt/seeds")
seed_dir.mkdir(parents=True, exist_ok=True)

df_sector_17.to_csv(
    seed_dir / "raw_jquants_sector_17.csv", index=False, quoting=csv.QUOTE_ALL
)
df_sector_33.to_csv(
    seed_dir / "raw_jquants_sector_33.csv", index=False, quoting=csv.QUOTE_ALL
)
df_market_segments.to_csv(
    seed_dir / "raw_jquants_market_segments.csv", index=False, quoting=csv.QUOTE_ALL
)
# %%
