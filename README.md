# Elevate Project Group 3 - HR System

Welcome to the **Elevate Project Group 3 HR System** repository. This project implements an intelligent multi-agent HR assistant designed to streamline employee HR interactions, policy inquiries, human capital management (HCM) operations, and service desk ticketing.

---

## 📄 System Design Document (SDD)

For detailed architectural specifications, data flows, and design rationale, please refer to the official System Design Document:
- 🔗 **[Elevate Project Group 3 SDD](https://docs.google.com/document/d/1xqh9OOcFJKYSywvI29MHQhwpdofpCaAF8td4-StcCtI/edit?tab=t.0)**

---

## 🏛️ Architecture Overview

The system is built on a multi-agent orchestration architecture featuring a centralized Master Agent and three specialized Sub-Agents:

```
                          ┌──────────────────────────┐
                          │    Root Orchestrator     │
                          │      (Master Agent)      │
                          └─────────────┬────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │                            │                            │
           ▼                            ▼                            ▼
┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
│    Policy Agent    │       │ WorkWeek HCM Agent │       │ServiceImmediately  │
│    (Sub-Agent)     │       │    (Sub-Agent)     │       │       Agent        │
└──────────┬─────────┘       └──────────┬─────────┘       └──────────┬─────────┘
           │                            │                            │
           ▼                            ▼                            ▼
┌────────────────────┐       ┌────────────────────┐       ┌────────────────────┐
│   Policy Service   │       │    WorkWeek HCM    │       │ServiceImmediately  │
│     MCP Server     │       │     MCP Server     │       │     MCP Server     │
└────────────────────┘       └────────────────────┘       └────────────────────┘
```

### 1. Master Agent: Root Orchestrator
- **Role:** Central entry point and coordinator for all user requests.
- **Responsibilities:**
  - Analyzes user intent, context, and conversation history.
  - Deconstructs complex, multi-step requests into actionable sub-tasks.
  - Dynamically routes requests to appropriate sub-agents (Policy Agent, WorkWeek HCM Agent, ServiceImmediately Agent).
  - Synthesizes findings and actions from sub-agents into a unified, coherent response to the user.

### 2. Specialized Sub-Agents

| Sub-Agent | Scope & Responsibilities | Key Capabilities / Tools |
| :--- | :--- | :--- |
| **Policy Agent** | Company policies, compliance, HR handbooks, benefits guidelines, and FAQs. | Policy knowledge search, RAG retrieval, policy clause verification. |
| **WorkWeek HCM Agent** | Core Human Capital Management (HCM) interactions and employee records. | Fetch employee profile, query leave/PTO balance, submit time-off requests, look up org charts. |
| **ServiceImmediately Agent** | HR and IT service desk workflows and ticketing. | Create support tickets, check ticket status, update incident records, track resolution progress. |

---

## 📁 Repository & Folder Structure

```
elevate-project-group3/
├── README.md                                  # Project overview and SDD documentation
└── src/
    ├── __init__.py                            # Main src package
    ├── main.py                                # System entrypoint
    ├── agents/                                # Agent definitions and logic
    │   ├── __init__.py
    │   ├── root_orchestrator/                 # Master Orchestrator Agent
    │   │   ├── __init__.py
    │   │   ├── agent.py                       # Root orchestrator agent implementation
    │   │   └── prompts.py                     # Orchestration prompts and routing instructions
    │   ├── policy_agent/                      # Policy Sub-Agent
    │   │   ├── __init__.py
    │   │   ├── agent.py                       # Policy agent implementation
    │   │   ├── prompts.py                     # Policy guidelines and persona prompts
    │   │   └── tools.py                       # Knowledge base search and retrieval tools
    │   ├── workweek_hcm_agent/                # WorkWeek HCM Sub-Agent
    │   │   ├── __init__.py
    │   │   ├── agent.py                       # WorkWeek HCM agent implementation
    │   │   ├── prompts.py                     # HCM agent prompts
    │   │   └── tools.py                       # HCM tools (PTO balance, time-off, profiles)
    │   └── service_immediately_agent/         # ServiceImmediately Sub-Agent
    │       ├── __init__.py
    │       ├── agent.py                       # ServiceImmediately agent implementation
    │       ├── prompts.py                     # Ticketing and service desk prompts
    │       └── tools.py                       # Service desk tools (ticket creation, status)
    ├── mcp_servers/                           # Model Context Protocol (MCP) servers
    │   ├── __init__.py
    │   ├── policy_service/                    # Policy RAG MCP Server
    │   │   ├── __init__.py
    │   │   └── server.py
    │   ├── workweek_hcm/                      # WorkWeek HCM MCP Server
    │   │   ├── __init__.py
    │   │   └── server.py
    │   └── service_immediately/              # ServiceImmediately MCP Server
    │       ├── __init__.py
    │       └── server.py
    └── shared/                                # Shared models, schemas, and configurations
        ├── __init__.py
        ├── config.py                          # Environment and model configurations
        └── models.py                          # Data models and request/response schemas
```

---

## 🚀 Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/26Kchiu/elevate-project-group3.git
   cd elevate-project-group3
   ```

2. **Explore Agents:**
   - Root Orchestrator: `src/agents/root_orchestrator/agent.py`
   - Policy Agent: `src/agents/policy_agent/agent.py`
   - WorkWeek HCM Agent: `src/agents/workweek_hcm_agent/agent.py`
   - ServiceImmediately Agent: `src/agents/service_immediately_agent/agent.py`
