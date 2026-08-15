# Infrastructure

単一のGoogle Cloudプロジェクトを1つのTerraform root moduleで管理します。Terraformが利用するstate bucketだけは、プロジェクトと同じく事前に手動作成します。

## 前提

- Billingと紐付いた空のGoogle Cloudプロジェクト
- Terraform 1.15.x
- gcloud CLI
- Terraformを実行するアカウントの必要なIAM権限

ローカルではサービスアカウントキーを作らず、Application Default Credentialsを利用します。

```bash
gcloud auth application-default login
```

## 初回セットアップ

プロジェクトIDを設定し、Terraform state用GCS bucketを一度だけ手動作成します。

```bash
export STOCK_ANALYTICS_PROJECT_ID="YOUR_GCP_PROJECT_ID"

gcloud services enable \
  serviceusage.googleapis.com \
  storage.googleapis.com \
  --project "$STOCK_ANALYTICS_PROJECT_ID"

gcloud storage buckets create \
  "gs://${STOCK_ANALYTICS_PROJECT_ID}-terraform-state" \
  --project "$STOCK_ANALYTICS_PROJECT_ID" \
  --location ASIA-NORTHEAST1 \
  --uniform-bucket-level-access \
  --public-access-prevention \
  --soft-delete-duration 7d

gcloud storage buckets update \
  "gs://${STOCK_ANALYTICS_PROJECT_ID}-terraform-state" \
  --versioning
```

続いてTerraformを初期化します。

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvarsのproject_idを変更する

terraform init \
  -backend-config="bucket=${STOCK_ANALYTICS_PROJECT_ID}-terraform-state"
terraform plan -out=terraform.tfplan
terraform apply terraform.tfplan
```

`terraform.tfvars`、state、planはGit管理対象外です。`apply`前にplan内容を確認してください。
