# Elevate Project Group 3 — HR Multi-Agent System & Policy Knowledge Engine

[![Architecture: BigQuery Graph + Google ADK](https://img.shields.io/badge/Architecture-BigQuery_GQL_Graph-blue.svg)](https://cloud.google.com/bigquery)
[![Model: Gemini 3.7 Flash](https://img.shields.io/badge/Model-Gemini_3.7_Flash-purple.svg)](https://deepmind.google/technologies/gemini/)
[![Project: elevate-taiwan-cohort-2](https://img.shields.io/badge/GCP_Project-elevate--taiwan--cohort--2-green.svg)](https://console.cloud.google.com/bigquery?project=elevate-taiwan-cohort-2)

This repository contains the **Elevate Project Group 3 HR Multi-Agent System**, featuring a deterministic **Policy Knowledge Agent** backed by a live **BigQuery Property Graph (GQL)** in Google Cloud project `elevate-taiwan-cohort-2`.

---

## 1. Project Architecture

```
elevate-project-group3/
├── README.md
├── src/
│   ├── main.py                         # System entrypoint
│   ├── shared/
│   │   ├── config.py                   # BigQuery dataset & model configuration
│   │   └── models.py                   # Pydantic data models
│   ├── agents/
│   │   ├── root_orchestrator/          # Master coordination agent
│   │   ├── policy_agent/               # Grounded Policy Reasoning Agent (3-Way Policy)
│   │   │   ├── agent.py
│   │   │   ├── prompts.py
│   │   │   └── tools.py
│   │   ├── workweek_hcm_agent/         # WorkWeek HCM sub-agent
│   │   └── service_immediately_agent/  # ServiceImmediately ITSM sub-agent
│   ├── mcp_servers/
│   │   ├── policy_service/             # Policy MCP Server for BigQuery Graph
│   │   │   └── server.py
│   │   ├── workweek_hcm/               # WorkWeek MCP Server
│   │   └── service_immediately/        # ServiceImmediately MCP Server
│   └── knowledge/                      # BigQuery Knowledge Management Layer
│       ├── graph_service.py            # BigQuery GQL & Vector engine
│       ├── curation_gate.py            # Human Curation Gate (Bands A-D)
│       ├── corpus/                     # Altostrat Singapore Handbook corpus & graph
│       └── ddl/                        # BigQuery SQL DDL for Nodes, Edges, & Graph
├── eval/                               # Golden Evaluation Benchmark (155 cases)
│   ├── evalset.json
│   └── eval_runner.py
├── tests/                              # Unit & Integration Tests (100% passing)
│   ├── test_policy_agent.py
│   └── test_curation_gate.py
└── infra/                              # Terraform Infrastructure as Code
    ├── main.tf
    ├── bigquery.tf
    └── variables.tf
```

---

## 2. Deployed BigQuery Knowledge Layer (`elevate-taiwan-cohort-2`)

The BigQuery Knowledge Engine is live in the **US multi-region** under project `elevate-taiwan-cohort-2`:

| Object | Type | Count | Description |
| :--- | :--- | :---: | :--- |
| `hr_knowledge.node_clause` | Node Table | 21 | Verbatim handbook policy statements |
| `hr_knowledge.node_entitlement` | Node Table | 17 | Benefit allowances (sick, vacation, childcare, etc.) |
| `hr_knowledge.node_condition` | Node Table | 9 | Predicate rules (tenure, child age limits) |
| `hr_knowledge.node_term` | Node Table | 4 | Glossary definitions |
| `hr_knowledge.edge_grants` | Edge Table | 17 | Maps clauses to granted entitlements |
| `hr_knowledge.edge_subject_to` | Edge Table | 9 | Maps entitlements to condition predicates |
| `hr_knowledge.edge_uses_term` | Edge Table | 4 | Maps clauses to glossary terms |
| `hr_knowledge.hr_policy_graph` | Property Graph | LIVE | BigQuery GQL Property Graph definition |
| `hr_analytics.audit_events_v1` | Partitioned Table | LIVE | Immutable audit log partitioned by date |

---

## 3. Running Evaluation Benchmark & Unit Tests

### Run the Evaluation Benchmark:
```bash
python3 -m eval.eval_runner
```

### Run Unit Tests:
```bash
python3 -m unittest discover -s tests
```
