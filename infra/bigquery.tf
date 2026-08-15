resource "google_bigquery_dataset" "stock_analytics" {
  project    = var.project_id
  dataset_id = "stock_analytics"
  location   = var.region

  friendly_name              = "Stock Analytics"
  description                = "Raw data and dbt models for stock analytics"
  delete_contents_on_destroy = false

  labels = {
    application = "stock-analytics"
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.bigquery]
}
