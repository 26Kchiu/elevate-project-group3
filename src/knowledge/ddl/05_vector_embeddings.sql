-- ============================================================================
-- 05_vector_embeddings.sql
-- Vector Embeddings Table & IVF Index over Curated Clause Chunks
-- ============================================================================

-- Generate embeddings for published clauses using text-embedding-005
CREATE OR REPLACE TABLE `hr_knowledge.clause_embeddings` AS
SELECT
  node_id,
  doc_id,
  clause_ref,
  title,
  verbatim_text,
  jurisdiction,
  ml_generate_embedding_result AS embedding
FROM ML.GENERATE_EMBEDDING(
  MODEL `hr_knowledge.embedding_model`,
  (
    SELECT
      node_id,
      doc_id,
      clause_ref,
      title,
      CONCAT(title, ': ', verbatim_text) AS content,
      jurisdiction
    FROM `hr_knowledge.node_clause`
    WHERE curation_state = 'published'
  ),
  STRUCT('RETRIEVAL_DOCUMENT' AS task_type)
);

-- Create Vector Search Index for Cosine Distance Nearest Neighbor Recall
CREATE OR REPLACE VECTOR INDEX `clause_vector_idx`
ON `hr_knowledge.clause_embeddings`(embedding)
OPTIONS(distance_type='COSINE', index_type='IVF');
