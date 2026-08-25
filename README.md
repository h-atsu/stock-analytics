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

## rawデータのBigQuery load

GCSへpublish済みのJ-Quants・Yahoo Finance日足を、日付partition単位でBigQueryへloadします。同じ日付の再実行はpartitionを置き換えるため、loadによる重複は発生しません。

```bash
uv run stock-analytics load daily-bars \
  --project YOUR_GCP_PROJECT_ID \
  --bucket YOUR_GCP_PROJECT_ID-stock-analytics-raw
```

作成されるrawテーブル:

- `raw_jquants_equity_daily_bars`（`Date` partition、`Code` cluster）
- `raw_yahoo_equity_daily_bars`（`trade_date` partition、`yahoo_ticker` cluster）

マスター、財務、決算予定、coverageを含む全raw artifactをloadする場合は、各テーブルを全置換します。初回bootstrap向けの処理です。

```bash
uv run stock-analytics load raw \
  --project YOUR_GCP_PROJECT_ID \
  --bucket YOUR_GCP_PROJECT_ID-stock-analytics-raw
```

## 初回bootstrap

localへの取得、GCS publish、BigQuery loadを順番に実行します。デフォルトでは、基準日の12週前を終端とするJ-Quants 2年分と、基準日までのYahoo Finance 5年分を取得します。

まず小期間で一巡確認します。

```bash
uv run stock-analytics bootstrap raw \
  --as-of 2026-08-16 \
  --project stock-analytics-505614 \
  --bucket stock-analytics-505614-stock-analytics-raw \
  --jquants-start-date 2026-05-18 \
  --yahoo-start-date 2026-08-10
```

確認後、開始日の上書きを外して全期間を実行します。

```bash
uv run stock-analytics bootstrap raw \
  --as-of 2026-08-16 \
  --project stock-analytics-505614 \
  --bucket stock-analytics-505614-stock-analytics-raw
```

正常なmanifestがあるJ-Quants partitionと、同一期間のYahoo coverageがあるrunはスキップします。途中で失敗した場合は、同じコマンドを再実行してください。休場日や開示データがない日は`no_data`として扱います。J-QuantsはFreeプランの毎分5リクエスト制限を超えないよう、リクエストごとに13秒間隔を空けます。429応答時は60秒、120秒、240秒の順に待機して再試行します。

## 日次パイプライン

JPX一覧の変更確認、J-Quantsの12週遅延日、Yahoo Financeの直近7暦日の取得、GCS publish、対象BigQuery partitionの置換、`dbt build`を直列実行します。

```bash
uv run stock-analytics pipeline daily \
  --as-of 2026-08-21 \
  --project stock-analytics-505614 \
  --bucket stock-analytics-505614-stock-analytics-raw
```

`--as-of`を省略するとAsia/Tokyoの当日を使用します。固定した日付を指定すれば、ローカルとCloud Run Jobで同じ対象期間を再実行できます。J-Quantsの休場日や開示データがない日は正常な`no_data`として扱い、Yahoo Financeと後続処理は継続します。検証またはdbt testが失敗した場合は非ゼロ終了します。

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

日次Cloud Run Jobは平日21時JSTに起動します。Cloud Runでは`--structured-logs`を有効にし、対象日、source、件数、欠損ticker数、所要時間をJSONでCloud Loggingへ記録します。Secretの手動登録、image push、Terraform applyの手順も[`infra/README.md`](infra/README.md)に記載しています。

J-QuantsとYahoo Financeのsource優先順位、暫定価格、企業行動による価格差、dbtの品質判定は[`docs/data-model.md`](docs/data-model.md)に記載しています。

## 開発時の検証

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run sqlfluff lint dbt/models dbt/tests
terraform fmt -check -recursive infra
```

pre-commitの有効化:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## dbt開発

rawテーブルから7つのstaging viewを作成し、vendor固有の列名・型を正規化します。local profileの準備やモデルのgrainは[`dbt/README.md`](dbt/README.md)を参照してください。

```bash
mkdir -p ~/.dbt
# profiles.ymlがすでにある場合はstock_analytics entryだけを追記する
cp dbt/profiles.yml.example ~/.dbt/profiles.yml
export GCP_PROJECT_ID=stock-analytics-505614
uv run dbt build --project-dir dbt --select tag:staging
```

日次パイプラインはリポジトリ内の`dbt/profiles.yml`を使用するため、Cloud RunではサービスアカウントのApplication Default Credentialsがそのまま使われます。

main branchのdbt関連ファイルを更新すると、GitHub Actionsがdbt Docsを生成してGitHub Pagesへ公開します。初回だけrepositoryのPages sourceを`GitHub Actions`へ設定してください。
