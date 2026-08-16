with source as (
    select * from {{ ref('raw_jquants_sector_17') }}
),

renamed as (
    select
        cast(S17 as string) as sector_17_code,
        trim(cast(S17Nm as string)) as sector_17_name,
        case trim(cast(S17NmEn as string))
            when 'AUTOMOBILES & TRANSPORTATION EQUIPMEN'
                then 'AUTOMOBILES & TRANSPORTATION EQUIPMENT'
            else trim(cast(S17NmEn as string))
        end as sector_17_name_en
    from source
)

select * from renamed
