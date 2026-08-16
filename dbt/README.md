# dbt development

BigQueryの`stock_analytics` dataset内で、`raw_`テーブルを`stg_` viewへ正規化します。環境別datasetやcustom schemaは、必要になるまで追加しません。

## 初期設定

Application Default Credentialsを設定します。

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project stock-analytics-505614
```

標準の`~/.dbt/profiles.yml`へprofileを作り、GCP projectを環境変数で指定します。

```bash
mkdir -p ~/.dbt
# profiles.ymlがすでにある場合はstock_analytics entryだけを追記する
cp dbt/profiles.yml.example ~/.dbt/profiles.yml
export GCP_PROJECT_ID=stock-analytics-505614
```

`DBT_DATASET`と`GCP_REGION`のデフォルトは、それぞれ`stock_analytics`と`asia-northeast1`です。

接続確認:

```bash
uv run dbt debug --project-dir dbt
```

## 開発コマンド

```bash
# 構文と依存関係だけを確認
uv run dbt parse --project-dir dbt

# raw sourceの更新時刻を確認
uv run dbt source freshness --project-dir dbt

# staging viewとdata testを構築
uv run dbt build --project-dir dbt --select +tag:staging

# コードマスターseedとそのstaging viewを構築
uv run dbt build --project-dir dbt --select raw_jquants_sector_17 raw_jquants_sector_33 raw_jquants_market_segments stg_jquants__sector_17 stg_jquants__sector_33 stg_jquants__market_segments

# SQLだけを再構築
uv run dbt run --project-dir dbt --select tag:staging

# stagingのdata testだけを実行
uv run dbt test --project-dir dbt --select tag:staging
```

`~/.dbt/profiles.yml`はGit管理しません。API keyやservice account keyをprofileへ保存せず、localではADC、Cloud Runではservice accountを使用します。

## SQLの検証とドキュメント

SQLFluffはBigQuery方言とdbt組み込みmacroを扱えるJinja templaterを使用します。lint時にBigQueryへ接続しません。

```bash
uv run sqlfluff lint dbt/models dbt/tests
uv run sqlfluff fix dbt/models dbt/tests
uv run dbt docs generate --project-dir dbt
uv run dbt docs serve --project-dir dbt
```

GitHub Actionsはmain branchのdbt関連ファイル更新時に、BigQueryへ接続せず空のcatalogでdbt Docsを生成してGitHub Pagesへ公開します。初回だけGitHubの`Settings > Pages > Build and deployment > Source`で`GitHub Actions`を選択してください。

Pages版には、project overview、source/model lineage、grain、data test、宣言済み列の説明が含まれます。`--empty-catalog`で生成するため、BigQueryから取得する物理型・行数などのcatalog metadataは含みません。ADCを使ってlocalで`dbt docs generate`を実行すると、実テーブルのcatalog metadataも確認できます。

モデルを追加・変更するときは、同じ変更で次を更新します。

- modelの責務とgrain
- 公開する全列のdescription
- business keyのunique testと必須列のnot null test
- source固有値、変換済み値、intermediate以降へ持ち越す責務の区別

複数modelで意味が同じ列は`dbt/docs/common_columns.md`のdoc blockを再利用します。projectのトップページは`dbt/docs/overview.md`で管理します。

## staging契約

モデル名は`stg_<source>__<entity>`とし、sourceとentityの境界を二重underscoreで表します。例: `stg_jquants__daily_bars`。

| model | grain |
|---|---|
| `stg_jquants__daily_bars` | `trade_date, security_code` |
| `stg_yahoo__daily_bars` | `trade_date, yahoo_ticker` |
| `stg_jquants__equity_master` | `snapshot_date, security_code` |
| `stg_jpx__listed_issues` | `snapshot_date, security_code` |
| `stg_jquants__financial_summary` | `disclosure_date, security_code, disclosure_number` |
| `stg_jquants__earnings_date` | `publication_date, security_code, fiscal_quarter_name` |
| `stg_yahoo__daily_bars_coverage` | `start_date, end_date, yahoo_ticker` |
| `stg_jquants__sector_17` | `sector_17_code` |
| `stg_jquants__sector_33` | `sector_33_code` |
| `stg_jquants__market_segments` | `market_code` |

すべてのstaging modelは、grainごとに`_ingested_at`が最新のraw行を採用します。vendor固有の列名はsnake_caseへ変換し、財務値は`safe_cast`で`numeric`へ変換します。

stagingでは価格調整、J-Quants優先、最新銘柄スナップショットの選択、財務指標計算を行いません。これらはintermediate以降の責務です。

コードマスターseedはJ-Quantsの列名と値を未加工で保持します。対応する`stg_jquants__*` viewでsnake_caseへの変換、文字列のtrim、既知の名称欠字の補正を行います。
