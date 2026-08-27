-- ============================================================================
-- 04_property_graph.sql
-- BigQuery Property Graph Definition (GQL Engine)
-- ============================================================================

CREATE OR REPLACE PROPERTY GRAPH `hr_knowledge.hr_policy_graph`
  NODE TABLES (
    `hr_knowledge.node_clause`
      KEY (node_id)
      LABEL Clause
      PROPERTIES (node_id, doc_id, version, clause_ref, title, verbatim_text, source_uri, page_number, jurisdiction, curation_state),
    `hr_knowledge.node_entitlement`
      KEY (node_id)
      LABEL Entitlement
      PROPERTIES (node_id, benefit_id, name, amount, unit, frequency, proratable, curation_state),
    `hr_knowledge.node_condition`
      KEY (node_id)
      LABEL Condition
      PROPERTIES (node_id, predicate, attribute, operator, target_value, description, curation_state),
    `hr_knowledge.node_term`
      KEY (node_id)
      LABEL Term
      PROPERTIES (node_id, term_name, definition, definition_clause_id, curation_state)
  )
  EDGE TABLES (
    `hr_knowledge.edge_grants`
      SOURCE KEY (src_clause_id) REFERENCES `hr_knowledge.node_clause` (node_id)
      DESTINATION KEY (dst_entitlement_id) REFERENCES `hr_knowledge.node_entitlement` (node_id)
      LABEL GRANTS,
    `hr_knowledge.edge_subject_to`
      SOURCE KEY (src_entitlement_id) REFERENCES `hr_knowledge.node_entitlement` (node_id)
      DESTINATION KEY (dst_condition_id) REFERENCES `hr_knowledge.node_condition` (node_id)
      LABEL SUBJECT_TO,
    `hr_knowledge.edge_uses_term`
      SOURCE KEY (src_clause_id) REFERENCES `hr_knowledge.node_clause` (node_id)
      DESTINATION KEY (dst_term_id) REFERENCES `hr_knowledge.node_term` (node_id)
      LABEL USES_TERM,
    `hr_knowledge.edge_excludes`
      SOURCE KEY (src_clause_id) REFERENCES `hr_knowledge.node_clause` (node_id)
      DESTINATION KEY (dst_condition_id) REFERENCES `hr_knowledge.node_condition` (node_id)
      LABEL EXCLUDES
  );
