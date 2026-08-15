# stock-analytics

J-Quantsから日本株データを取得し、BigQueryとdbtで分析するためのプロジェクトです。

## 株価日足の取得

`.env`にJ-Quants APIキーを設定します。

```dotenv
JQUANTS_API_KEY=
```

指定した1営業日分を検証し、日別Parquetとmanifestへ保存します。

```bash
uv run stock-analytics ingest daily-bars --date 2024-07-25
```

出力先を変更する場合:

```bash
uv run stock-analytics ingest daily-bars \
  --date 2024-07-25 \
  --output-dir data/raw/jquants
```

## 銘柄マスターの取得

指定した基準日時点のJ-Quants銘柄マスターを検証し、日別Parquetとmanifestへ保存します。

```bash
uv run stock-analytics ingest equity-master --date 2024-07-25
```

出力先を変更する場合:

```bash
uv run stock-analytics ingest equity-master \
  --date 2024-07-25 \
  --output-dir data/raw/jquants
```

## 財務サマリーの取得

指定した開示日のJ-Quants財務サマリーを検証し、日別Parquetとmanifestへ保存します。

```bash
uv run stock-analytics ingest financial-summary --date 2024-07-25
```

出力先を変更する場合:

```bash
uv run stock-analytics ingest financial-summary \
  --date 2024-07-25 \
  --output-dir data/raw/jquants
```

## 決算発表予定日の取得

指定した公表日に登録・変更された決算発表予定日を検証し、履歴として保存します。

```bash
uv run stock-analytics ingest earnings-date --date 2024-07-25
```

出力先を変更する場合:

```bash
uv run stock-analytics ingest earnings-date \
  --date 2024-07-25 \
  --output-dir data/raw/jquants
```

## JPX現行上場銘柄一覧の取得

JPX公式ページから現行のExcelを取得し、原本と正規化Parquetを保存します。同じExcelが保存済みの場合はスキップします。

```bash
uv run stock-analytics ingest listed-issues
```

出力先を変更する場合:

```bash
uv run stock-analytics ingest listed-issues --output-dir data/raw/jpx
```

4桁の銘柄コードにはYahoo ticker候補として`.T`を付与します。5桁の種類株式は誤った銘柄へ対応付けないため、Yahoo tickerをnullにします。

## Yahoo Finance日足の取得

最新のJPX上場銘柄一覧にあるYahoo ticker候補を使い、raw OHLC、調整後終値、出来高、配当、株式分割、capital gainsを取得します。開始日と終了日はどちらも包含です。

```bash
uv run stock-analytics ingest yahoo-daily-bars \
  --start-date 2026-08-03 \
  --end-date 2026-08-10
```

JPX一覧や出力先を変更する場合:

```bash
uv run stock-analytics ingest yahoo-daily-bars \
  --start-date 2026-08-03 \
  --end-date 2026-08-10 \
  --listed-issues-dir data/raw/jpx \
  --output-dir data/raw/yfinance
```

取得結果は取引日別Parquet、tickerごとの取得可否はcoverage Parquetへ保存します。Yahoo Financeデータは個人・研究用途の暫定補完として扱います。

## raw artifactのGCS publish

`data/raw`配下の`data.parquet`と対応する`manifest.json`をGCSへpublishします。ParquetはmanifestのSHA-256と照合し、同じobjectが存在する場合は上書きせずスキップします。

```bash
uv run stock-analytics publish raw \
  --bucket YOUR_GCP_PROJECT_ID-stock-analytics-raw
```

出力元を変更する場合:

```bash
uv run stock-analytics publish raw \
  --bucket YOUR_GCP_PROJECT_ID-stock-analytics-raw \
  --source-dir data/raw
```

## Docker実行

Cloud Run Jobで使用する本番イメージをローカルでビルドできます。`.env`と取得済みデータはイメージに含まれません。

```bash
docker build -t stock-analytics:local .
docker run --rm stock-analytics:local --help
```

J-Quantsの取得時は、ローカルの`.env`を環境変数として渡し、出力先をmountします。

```bash
docker run --rm \
  --env-file .env \
  --mount type=bind,source="$PWD/data",target=/app/data \
  stock-analytics:local \
  ingest daily-bars --date 2024-07-25
```

## GCPインフラ

Terraform構成は`infra/`直下で管理します。初回のstate bucket作成とGCS backendへの移行手順は[`infra/README.md`](infra/README.md)を参照してください。

## 開発時の検証

```bash
uv run pytest
uv run ruff check .
uv run ty check
```

## dbtマスターseed

分析で利用する小規模なコードマスターを`dbt/seeds`で管理します。

- JPX 17業種区分
- JPX 33業種区分と17業種区分の対応
- JPX市場区分（過去区分を含む）

BigQuery環境とdbt profileの構築後、次のコマンドで投入・検証します。

```bash
uv run dbt seed --project-dir dbt
uv run dbt test --project-dir dbt --select resource_type:seed
```
