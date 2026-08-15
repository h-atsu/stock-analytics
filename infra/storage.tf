resource "google_storage_bucket" "raw_data" {
  name     = "${var.project_id}-stock-analytics-raw"
  project  = var.project_id
  location = upper(var.region)

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  labels = {
    application = "stock-analytics"
    managed_by  = "terraform"
    purpose     = "raw-data"
  }

  depends_on = [google_project_service.storage]
}
