variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
  default     = "elevate-taiwan-cohort-2"
}

variable "region" {
  type        = string
  description = "Google Cloud primary region"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment (development, staging, production)"
  default     = "production"
}

variable "knowledge_dataset_id" {
  type        = string
  description = "BigQuery Knowledge Management Layer Dataset ID"
  default     = "hr_knowledge"
}

variable "analytics_dataset_id" {
  type        = string
  description = "BigQuery Audit & Telemetry Dataset ID"
  default     = "hr_analytics"
}

variable "policy_corpus_bucket" {
  type        = string
  description = "GCS bucket hosting active policy PDFs"
  default     = "hr-policy-corpus"
}

variable "telemetry_dlq_bucket" {
  type        = string
  description = "GCS bucket for telemetry dead-letter queue spillover"
  default     = "hr-agent-telemetry-dlq"
}
