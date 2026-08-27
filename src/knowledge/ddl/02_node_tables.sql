-- ============================================================================
-- 02_node_tables.sql
-- BigQuery Node Tables for HR Policy Graph Ontology (15 Node Schema)
-- ============================================================================

-- 1. Clause Node: Atomic legal or policy statement with provenance
CREATE TABLE IF NOT EXISTS `hr_knowledge.node_clause` (
  node_id STRING NOT NULL,
  doc_id STRING NOT NULL,
  version INT64 NOT NULL,
  clause_ref STRING NOT NULL,          -- e.g., '1.1', '1.2.3', '3.1'
  title STRING,                        -- e.g., 'Outpatient Sick Time & Hospitalization Leave'
  verbatim_text STRING NOT NULL,       -- Exact source clause text
  source_uri STRING NOT NULL,          -- gcs URI or source doc reference
  page_number INT64,
  section_ref STRING,                  -- e.g., 'SECTION 1: PAID TIME OFF & LEAVE OPERATIONS'
  jurisdiction STRING NOT NULL,        -- 'SG', 'AU', 'UK', 'global'
  curation_state STRING NOT NULL,      -- 'proposed', 'in_review', 'published', 'rejected', 'superseded'
  curated_by STRING,                   -- LDAP / email of human curator
  curated_at TIMESTAMP,
  extraction_confidence FLOAT64,       -- 0.0 to 1.0 (Band A/B/C/D)
  effective_date DATE,
  expiry_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 2. Entitlement Node: Quantified benefits, allowances, and rights
CREATE TABLE IF NOT EXISTS `hr_knowledge.node_entitlement` (
  node_id STRING NOT NULL,
  benefit_id STRING NOT NULL,          -- e.g., 'outpatient_sick_leave', 'vacation_leave_tier1', 'bereavement_leave'
  name STRING NOT NULL,                -- Human-readable benefit name
  amount FLOAT64 NOT NULL,             -- Numeric allowance quantity (e.g. 14.0, 20.0, 500.0)
  unit STRING NOT NULL,                -- 'days', 'weeks', 'work_days', 'USD', 'SGD'
  frequency STRING,                    -- 'per_calendar_year', 'per_event', 'per_lifetime', 'one_off'
  proratable BOOLEAN DEFAULT FALSE,
  curation_state STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 3. Condition Node: Evaluable predicates & prerequisite criteria
CREATE TABLE IF NOT EXISTS `hr_knowledge.node_condition` (
  node_id STRING NOT NULL,
  predicate STRING NOT NULL,           -- e.g., 'tenure_years >= 1 AND tenure_years <= 6'
  attribute STRING NOT NULL,           -- e.g., 'tenure_years', 'employment_type', 'absence_duration_days'
  operator STRING NOT NULL,            -- 'EQUALS', 'GREATER_THAN_OR_EQUAL', 'LESS_THAN', 'BETWEEN', 'IN'
  target_value STRING NOT NULL,        -- e.g., '1-6', 'permanent', '>2'
  description STRING,
  curation_state STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 4. Term Node: Domain definitions and glossary concepts
CREATE TABLE IF NOT EXISTS `hr_knowledge.node_term` (
  node_id STRING NOT NULL,
  term_name STRING NOT NULL,           -- e.g., 'immediate_family', 'hospitalization', 'shift_worker'
  definition STRING NOT NULL,          -- Verbatim definition text from policy
  definition_clause_id STRING NOT NULL,-- Foreign key to source clause
  curation_state STRING NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
