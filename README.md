# Sentinel — AI GRC Auditor Agent

Sentinel is an autonomous AI Governance, Risk, and Compliance (GRC) auditor that evaluates deployed AI agents against **GDPR** and the **EU AI Act** using a structured Workflow Graph architecture.

Built for the **Google Cloud Rapid Agent Hackathon (Arize Track), June 2026.**

---

## Agent Engineering Framework Alignment

Sentinel is structured according to the Agent Engineering Framework:

| Framework Phase | Sentinel Implementation |
|----------------|------------------------|
| Phase 1 — Problem Decomposition | `PROBLEM_STATEMENT.md` |
| Phase 3 — System Design (6 layers) | `ARCHITECTURE.md` |
| Phase 4 — Tool Design | `TOOL_CATALOG.md` |
| Phase 5 — Reflection (Level 2) | `backend/agent/reflection.py` |
| Phase 6 — Evaluation Framework | `backend/eval/` |
| Phase 7 — Error Analysis | `backend/eval/error_analysis.py` |
| Phase 8 — Observability | `structlog` + Arize tracing throughout |
| Phase 9 — Pattern 3 Workflow Graph | `backend/agent/orchestrator.py` |

---

## Workflow Graph

```
Audit Request
      ↓
   PLANNER        — validates modules, confirms tools
      ↓
  RETRIEVER       — Arize MCP traces, Elastic MCP logs
      ↓
  EXECUTOR        — 3 compliance modules in sequence
      ↓
  REFLECTOR       — Level 2 citation/PII/specificity checks
      ↓
   SCORER         — weighted aggregation (40/40/20)
      ↓
  REPORTER        — PDF + JSON + live dashboard
```

---

## Hackathon Requirements

| Requirement | Implementation |
|-------------|---------------|
| Google Cloud Agent Builder | Google Gemini 1.5 Flash (hallucination scorer) |
| Gemini | `langchain-google-genai` in `orchestrator.py` |
| Arize MCP | `agent/tools/arize_tool.py` (traces + spans) |
| Elastic MCP | `agent/tools/elastic_tool.py` (PII log scanning) |
| GDPR compliance module | `modules/pii_leakage.py` + `policies/gdpr.json` |
| EU AI Act compliance module | `modules/prompt_injection.py`, `modules/hallucination.py` + `policies/eu_ai_act.json` |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Agent Core | Custom Workflow Graph + Gemini 1.5 Flash |
| API | FastAPI 0.111 (Python 3.11) |
| Frontend | Next.js 14 + Tailwind CSS |
| Arize Integration | Arize REST API (MCP Resource) |
| Elastic Integration | Elasticsearch Python client (MCP Resource) |
| PDF Generation | WeasyPrint + Jinja2 |
| Storage | Local filesystem (dev) / Google Cloud Storage (prod) |
| Deployment | Google Cloud Run |
| Observability | structlog + Arize trace export |

---

## Quick Start — No Docker (Recommended on Windows)

```bash
# Windows PowerShell
.\setup.ps1

# macOS / Linux
bash setup.sh
```

Then open 3 terminals:

```
Terminal 1:  cd backend && .\.venv\Scripts\Activate.ps1 && uvicorn main:app --port 8000 --reload
Terminal 2:  cd mock_agent && uv run uvicorn main:app --host 0.0.0.0 --port 8001
Terminal 3:  cd frontend && npm run dev
```

Open **http://localhost:3000**, enter `http://localhost:8001/chat` as the target, and click **RUN AUDIT**.

→ Full instructions: **`no-docker-setup.md`**

---

## Quick Start — Docker

```bash
cp .env.example .env   # add your credentials
docker-compose up -d
open http://localhost:3000
```

---

## Project Structure

```
sentinel/
├── PROBLEM_STATEMENT.md     # Framework Phase 1 — problem decomposition
├── ARCHITECTURE.md          # Framework Phase 3 — six-layer system design
├── TOOL_CATALOG.md          # Framework Phase 4 — tool specs
├── no-docker-setup.md       # Windows + macOS + Linux setup guide
├── setup.ps1                # Windows PowerShell setup script
├── setup.sh                 # macOS / Linux setup script
│
├── backend/
│   ├── agent/
│   │   ├── orchestrator.py  # Workflow Graph — 6 stages
│   │   ├── state.py         # State machine (AuditContext)
│   │   ├── reflection.py    # Level 2 Reflection validators
│   │   ├── prompts.py       # LLM prompt templates
│   │   └── tools/           # Arize, Elastic, Target, Policy tools
│   ├── modules/             # Compliance test modules
│   │   ├── prompt_injection.py  # EU AI Act Art.15
│   │   ├── pii_leakage.py       # GDPR Art.5/25/32
│   │   └── hallucination.py     # EU AI Act Annex III
│   ├── output/              # PDF, JSON, GCS storage
│   ├── policies/            # GDPR + EU AI Act rule library (JSON)
│   ├── eval/                # Framework Phase 6 — evaluation suite
│   │   ├── dataset.json     # 20 ground-truth eval cases
│   │   ├── runner.py        # Eval runner (python -m eval.runner)
│   │   ├── error_analysis.py # Phase 7 — error categorisation
│   │   └── EVALUATION.md    # Eval strategy documentation
│   └── tests/               # 18+ unit + integration tests
│
├── frontend/                # Next.js 14 live audit dashboard
├── mock_agent/              # Deliberately vulnerable demo target
├── docker-compose.yml       # All 3 services
└── .github/workflows/ci.yml # Test → Lint → Cloud Run deploy
```

---

## Running Tests

```bash
cd backend
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
pytest --tb=short -q
```

## Running the Eval Suite

```bash
cd backend && python -m eval.runner
```

## Running Error Analysis

```bash
cd backend && python -m eval.error_analysis
```

---

## Compliance Modules

| Module | Tests | Regulatory Mapping |
|--------|-------|--------------------|
| Prompt Injection Resistance | 22 adversarial probes, 4 categories | EU AI Act Art.15, EUAIA-Art9 |
| PII Leakage Detection | 6 PII types, Arize + Elastic sources | GDPR Art.5(1)(c), Art.25, Art.32 |
| Hallucination / Accuracy Risk | Gemini + local fallback scorer | EU AI Act Annex III, Art.13 |

---

## Observability

Every stage is timed and logged via `structlog`. The completed report includes:

```json
{
  "reflection": {
    "quality": "good",
    "citation_errors": 0,
    "pii_leaks_in_evidence": 0,
    "warnings": []
  },
  "timing": {
    "planning":   {"status": "complete", "duration_ms": 12.1},
    "retrieving": {"status": "complete", "duration_ms": 340.5},
    "executing":  {"status": "complete", "duration_ms": 8200.0},
    "reflecting": {"status": "complete", "duration_ms": 18.3},
    "scoring":    {"status": "complete", "duration_ms": 1.2},
    "reporting":  {"status": "complete", "duration_ms": 1100.4}
  }
}
```

---

## Environment Variables

See `.env.example` for all options. Minimum required to run with mock data:

```env
ENVIRONMENT=development
STORAGE_BACKEND=local
```

Optional (real data sources):

```env
GOOGLE_API_KEY=        # Gemini hallucination scoring
ARIZE_API_KEY=         # Arize MCP trace data
ARIZE_SPACE_KEY=
ELASTIC_API_KEY=       # Elastic MCP log scanning
ELASTIC_CLOUD_ID=
GCS_BUCKET_NAME=       # Google Cloud Storage (production)
```

---

## License

MIT — see [LICENSE](LICENSE)
