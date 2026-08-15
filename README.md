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

## 開発時の検証

```bash
uv run pytest
uv run ruff check .
uv run ty check
```
