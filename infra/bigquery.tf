# BigQuery Knowledge & Analytics Datasets in US Multi-Region
resource "google_bigquery_dataset" "knowledge_dataset" {
  dataset_id                  = var.knowledge_dataset_id
  friendly_name               = "HR Knowledge Management Layer"
  description                 = "Stores policy object tables, parsed layouts, property graph nodes/edges, and vector embeddings."
  location                    = "US"
  delete_contents_on_destroy  = false
}

resource "google_bigquery_dataset" "analytics_dataset" {
  dataset_id                  = var.analytics_dataset_id
  friendly_name               = "HR Agent Analytics & Audit Sink"
  description                 = "Stores immutable audit events and session telemetry partitioned by date with 90-day retention."
  location                    = "US"
  delete_contents_on_destroy  = false
}

# Cloud Storage Bucket for Policy Corpus
resource "google_storage_bucket" "policy_corpus" {
  name                        = "${var.project_id}-${var.policy_corpus_bucket}"
  location                    = "US"
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
}

# Cloud Storage Bucket for Telemetry DLQ
resource "google_storage_bucket" "telemetry_dlq" {
  name                        = "${var.project_id}-${var.telemetry_dlq_bucket}"
  location                    = "US"
  uniform_bucket_level_access = true
}
