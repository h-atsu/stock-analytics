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
