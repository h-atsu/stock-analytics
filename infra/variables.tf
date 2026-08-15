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
