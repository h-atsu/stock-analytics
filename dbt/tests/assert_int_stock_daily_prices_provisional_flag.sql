select *
from {{ ref('int_stock__daily_prices') }}
where is_provisional != (price_source = 'yahoo')
