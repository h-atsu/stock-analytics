select *
from {{ ref('int_stock__daily_prices') }}
where
    (has_jquants and price_source != 'jquants')
    or (not has_jquants and has_yahoo and price_source != 'yahoo')
