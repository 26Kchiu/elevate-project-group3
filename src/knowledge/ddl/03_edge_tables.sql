-- ============================================================================
-- 03_edge_tables.sql
-- BigQuery Edge Tables for HR Policy Graph Relationships (21 Edge Schema)
-- ============================================================================

-- 1. GRANTS Edge: Clause -> Entitlement
CREATE TABLE IF NOT EXISTS `hr_knowledge.edge_grants` (
  edge_id STRING NOT NULL,
  src_clause_id STRING NOT NULL,
  dst_entitlement_id STRING NOT NULL,
  curation_state STRING NOT NULL DEFAULT 'published',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 2. SUBJECT_TO Edge: Entitlement -> Condition
CREATE TABLE IF NOT EXISTS `hr_knowledge.edge_subject_to` (
  edge_id STRING NOT NULL,
  src_entitlement_id STRING NOT NULL,
  dst_condition_id STRING NOT NULL,
  curation_state STRING NOT NULL DEFAULT 'published',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 3. USES_TERM Edge: Clause -> Term
CREATE TABLE IF NOT EXISTS `hr_knowledge.edge_uses_term` (
  edge_id STRING NOT NULL,
  src_clause_id STRING NOT NULL,
  dst_term_id STRING NOT NULL,
  curation_state STRING NOT NULL DEFAULT 'published',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 4. EXCLUDES Edge: Clause -> Condition / Group
CREATE TABLE IF NOT EXISTS `hr_knowledge.edge_excludes` (
  edge_id STRING NOT NULL,
  src_clause_id STRING NOT NULL,
  dst_condition_id STRING NOT NULL,
  curation_state STRING NOT NULL DEFAULT 'published',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- 5. SUPERSEDES Edge: Clause -> Prior Clause
CREATE TABLE IF NOT EXISTS `hr_knowledge.edge_supersedes` (
  edge_id STRING NOT NULL,
  src_clause_id STRING NOT NULL,
  dst_clause_id STRING NOT NULL,
  superseded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
