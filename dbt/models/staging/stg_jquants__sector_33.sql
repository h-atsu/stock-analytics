with source as (
    select * from {{ ref('raw_jquants_sector_33') }}
),

renamed as (
    select
        cast(S33 as string) as sector_33_code,
        trim(cast(S33Nm as string)) as sector_33_name,
        trim(cast(S33NmEn as string)) as sector_33_name_en,
        cast(S17 as string) as sector_17_code
    from source
)

select * from renamed
