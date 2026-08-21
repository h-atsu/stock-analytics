output "artifact_registry_repository_url" {
  description = "Artifact Registry Docker repository URL"
  value       = "${google_artifact_registry_repository.docker.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset used by raw tables and dbt models"
  value       = google_bigquery_dataset.stock_analytics.dataset_id
}

output "raw_data_bucket_name" {
  description = "GCS bucket for validated raw ingestion artifacts"
  value       = google_storage_bucket.raw_data.name
}

output "daily_job_service_account_email" {
  description = "Service account used by the daily Cloud Run Job"
  value       = google_service_account.daily_job.email
}

output "jquants_secret_id" {
  description = "Existing Secret Manager secret used for the J-Quants API key"
  value       = data.google_secret_manager_secret.jquants_api_key.secret_id
}

output "daily_job_name" {
  description = "Cloud Run Job name"
  value       = google_cloud_run_v2_job.daily.name
}
