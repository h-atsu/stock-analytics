# %%
from datetime import datetime

import jquantsapi
from dateutil import tz
from dotenv import load_dotenv

# %%
load_dotenv()

cli = jquantsapi.ClientV2()
df = cli.get_eq_bars_daily_range(
    start_dt=datetime(2024, 7, 25, tzinfo=tz.gettz("Asia/Tokyo")),
    end_dt=datetime(2024, 7, 25, tzinfo=tz.gettz("Asia/Tokyo")),
)
print(df)
# %%
