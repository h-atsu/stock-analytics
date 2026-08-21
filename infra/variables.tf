variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "Default region for regional resources"
  type        = string
  default     = "asia-northeast1"
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID for Docker images"
  type        = string
  default     = "stock-analytics"
}

variable "daily_job_image_name" {
  description = "Docker image name in the Artifact Registry repository"
  type        = string
  default     = "stock-analytics"
}

variable "daily_job_image_tag" {
  description = "Docker image tag deployed to the daily Cloud Run Job"
  type        = string
  default     = "latest"
}

variable "daily_job_schedule" {
  description = "Cloud Scheduler cron expression interpreted in Asia/Tokyo"
  type        = string
  default     = "0 21 * * 1-5"
}

variable "alert_email" {
  description = "Email address notified when the daily job logs an error"
  type        = string
}
