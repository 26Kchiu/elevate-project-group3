# WorkAgent — WorkWeek HCM Virtual Assistant

An enterprise conversational AI agent built with **Google ADK** (Agent Development Kit) and **Gemini 3.7 / 2.5 Flash** to interface with the **WorkWeek SaaS** Human Capital Management platform.

Developed in compliance with the **Finalized Software Design Document (SDD v2.0.0)**.

---

## 🌟 Key Capabilities

1. **System-of-Record Profile Retrieval:**
   - Real-time querying of employee records (name, title, department, manager, location, contact details).
2. **Accurate Leave Balance Queries:**
   - Fetches live balances across Vacation, Sick, Medical, Bereavement, and Professional Study leave.
3. **Confirm-Before-Commit Protocol (SDD Section 4.2):**
   - Mutating actions (e.g. Leave Submissions, Contact Info Updates) are staged with a **SHA-256 cryptographic payload hash** and a single-use 5-minute confirmation token.
   - Prevents unauthorized writes, prompt injections, and accidental commits.
4. **Model Context Protocol (MCP) Integration:**
   - Configured to communicate via Model Context Protocol (MCP) over SSE/HTTP to the WorkWeek SaaS service (`https://mock-saas.aishprabhat.demo.altostrat.com/`) using dynamically minted MCP tokens derived from Corporate SSO sessions (`login.corp.google.com`).
   - Built-in resilient local emulator fallback for offline development, local testing, and automated CI/CD pipelines.
5. **Interactive Web GUI:**
   - Modern, responsive chat UI featuring real-time persona switching, system-of-record badges, interactive confirmation cards, and quick action prompts.

---

## 📁 Repository Structure

```
work-agent/
├── src/
│   ├── __init__.py
│   ├── agent.py              # Google ADK LlmAgent, Tool definitions, and System Prompt
│   ├── app.py                # FastAPI backend & REST API endpoints
│   ├── security.py           # Confirm-Before-Commit & SHA-256 Token Manager
│   └── workweek_service.py   # WorkWeek MCP client & HCM data provider
├── static/
│   ├── app.js                # Frontend application logic & interactive cards
│   ├── index.html            # Web GUI chat surface (WCAG 2.2 AA compliant)
│   └── styles.css            # Google Cloud styling & dark/light theme
├── tests/
│   └── test_work_agent.py    # Comprehensive test suite (Accuracy, Security, & E2E)
├── requirements.txt          # Python dependencies
├── run_local.sh              # One-click startup script
└── README.md                 # Project documentation
```

---

## 🚀 Quickstart & Local Execution

### 1. Prerequisites
- Python 3.11+
- Active Google Cloud SDK authentication (`gcloud auth login`)

### 2. Installation
```bash
cd work-agent
pip install -r requirements.txt
```

### 3. Run Test Suite
```bash
pytest tests/ -v
```

### 4. Start the Local Web Application
```bash
chmod +x run_local.sh
./run_local.sh
```
Or directly with uvicorn:
```bash
python -m uvicorn src.app:app --host 0.0.0.0 --port 8080 --reload
```
Open your browser at **http://localhost:8080** to test interactively!

---

## 🔒 Security Architecture (SDD Highlights)

* **Server-Side Identity Injection (ADR-005):** User employee identity is bound server-side from session context, preventing client identity spoofing.
* **Payload Hash Verification:** Confirmation tokens are mathematically bound to `SHA256(canonical_json(payload))`. Any change in parameters causes rejection with `409_PAYLOAD_TAMPERED`.
* **Replay Protection:** Tokens are single-use and invalidated immediately upon first execution.
