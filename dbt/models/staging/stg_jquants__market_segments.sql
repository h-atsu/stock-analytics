with source as (
    select * from {{ ref('raw_jquants_market_segments') }}
),

renamed as (
    select
        cast(Mkt as string) as market_code,
        trim(cast(MktNm as string)) as market_name,
        trim(cast(MktNmEn as string)) as market_name_en
    from source
)

select * from renamed
