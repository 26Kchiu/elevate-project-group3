-- ============================================================================
-- 01_dataset_and_connections.sql
-- HR Knowledge Dataset, GCS External Connection, Object Table & Remote Model
-- ============================================================================

-- Create BigQuery Datasets in US Multi-Region (ADR-006)
CREATE SCHEMA IF NOT EXISTS `hr_knowledge`
OPTIONS (
  location = 'US',
  description = 'Knowledge Management Layer storing policy objects, parsed documents, ontology graph nodes/edges, and vector embeddings.'
);

CREATE SCHEMA IF NOT EXISTS `hr_analytics`
OPTIONS (
  location = 'US',
  description = 'Telemetry and audit events dataset partitioned by date with 90-day retention.'
);

-- External Object Table indexing policy PDF corpus in Cloud Storage
CREATE EXTERNAL TABLE IF NOT EXISTS `hr_knowledge.policy_objects`
WITH CONNECTION `us.docai_connection`
OPTIONS (
  object_metadata = 'SIMPLE',
  uris = ['gs://hr-policy-corpus/active/*.pdf', 'gs://hr-policy-corpus/active/*.md']
);

-- Remote Document AI Layout Parser Model Reference
CREATE OR REPLACE MODEL `hr_knowledge.docai_layout_parser`
REMOTE WITH CONNECTION `us.docai_connection`
OPTIONS (
  remote_service_type = 'DOCUMENT_AI',
  document_ai_processor = 'projects/hr-agent-mvp-prod/locations/us/processors/layout-parser-default'
);

-- Remote Text Embedding Model Reference
CREATE OR REPLACE MODEL `hr_knowledge.embedding_model`
REMOTE WITH CONNECTION `us.vertex_ai_connection`
OPTIONS (
  endpoint = 'text-embedding-005'
);

-- Parsed Documents Layout Output Table
CREATE OR REPLACE TABLE `hr_knowledge.parsed_documents` (
  uri STRING NOT NULL,
  doc_id STRING NOT NULL,
  version INT64 NOT NULL,
  jurisdiction STRING,
  parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  layout_result JSON
)
PARTITION BY DATE(parsed_at)
CLUSTER BY doc_id, version;
