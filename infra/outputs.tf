output "artifact_registry_repository_url" {
  description = "Artifact Registry Docker repository URL"
  value       = "${google_artifact_registry_repository.docker.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset used by raw tables and dbt models"
  value       = google_bigquery_dataset.stock_analytics.dataset_id
}
