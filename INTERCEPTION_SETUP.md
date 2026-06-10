# Sentinel Inline Interception — Setup & Configuration Guide

Sentinel now includes an **Inline Interception Proxy**. This system allows real-time auditing and active enforcement of compliance policies (GDPR and EU AI Act) on live agent LLM traffic. 

Unlike the passive audit pipeline (which runs offline scans on Arize traces and Elastic logs), the Interception Proxy runs inline as a transparent proxy server, evaluating messages, redacting PII, and blocking injection attempts **before** they reach the upstream LLM provider.

---

## 1. Architectural Overview

```
Target Agent  ──(POST /chat/completions)──►  Sentinel Proxy (e.g., :8787)
                                                    │
                                                    ▼
                                            Compliance Adapter
                                            • PII Detection
                                            • Prompt Injection Check
                                                    │
                             ┌──────────────────────┴──────────────────────┐
                      [Verdict: BLOCK]                               [Verdict: ALLOW/REDACT]
                             │                                             │
                             ▼                                             ▼
                      403 Forbidden                                  Forensic Ledger
                (Returns error to Agent)                            (Digests & Metadata Only)
                                                                           │
                                                                           ▼
                                                                     Forward Upstream
                                                                (Real LLM, e.g. OpenAI)
```

1. **Proxy Server (FastAPI + Uvicorn)**: Spun up dynamically inside the main Sentinel process as a background task. It listens on a configurable local port and exposes OpenAI-compatible endpoint paths (e.g., `/v1/chat/completions`).
2. **Compliance Adapter**: Performs direct, minimal-latency scans (< 5ms) on incoming payloads by leveraging the internal regex and scanning patterns from the `pii_leakage` and `prompt_injection` modules.
3. **Forensic Ledger**: Durably writes transaction summaries to an append-only JSONL log. To comply with GDPR Article 5(1)(e), only SHA-256 digests of the payloads and PII type names are saved; raw PII never hits disk.
4. **LLM Dispatcher**: Forwards the sanitized (potentially redacted) request to the actual upstream LLM and pipes back the streaming or non-streaming completion response.

---

## 2. Quick Start

### Step 1: Start Sentinel Backend
Start the main Sentinel API server:
```bash
cd backend
# Activate virtual environment
.\.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate      # macOS/Linux

# Start FastAPI
uvicorn main:app --port 8000 --reload
```

### Step 2: Start an Ephemeral Intercept Session
Sentinel supports spawning multiple proxy sessions concurrently. Create a session by posting to the Intercept API endpoint:

```bash
curl -X POST "http://localhost:8000/api/v1/intercept/session" \
     -H "Content-Type: application/json" \
     -d '{
       "upstream_llm_url": "https://api.openai.com/v1",
       "upstream_api_key": "your-openai-api-key",
       "proxy_port": 8787,
       "block_on_pii": false,
       "block_on_injection": true
     }'
```

**Request Parameters**:
* `upstream_llm_url`: The real LLM base URL. Allows per-session target providers.
* `upstream_api_key` *(optional)*: The token for the upstream LLM. If omitted, falls back to the backend's `OPENAI_API_KEY` environment variable.
* `proxy_port` *(optional, default: 8787)*: The preferred local port. If the port is already in use, Sentinel will automatically scan upwards to find the next available port.
* `block_on_pii` *(optional, default: false)*: If `true`, any PII leak causes an immediate `403 Forbidden` response. If `false`, PII is silently redacted/masked and forwarded.
* `block_on_injection` *(optional, default: true)*: If `true`, any detected injection pattern blocks the request immediately with a `403 Forbidden`.

**Example Response**:
```json
{
  "session_id": "caacf8aa-2036-4fb8-9aae-78b74bb1e456",
  "status": "running",
  "proxy_port": 8787,
  "proxy_base_url": "http://127.0.0.1:8787/v1",
  "ledger_path": "C:\\Users\\ADMIN\\Documents\\...\\backend\\ledger\\data\\caacf8aa-2036-4fb8-9aae-78b74bb1e456\\transactions.jsonl",
  "upstream_llm_url": "https://api.openai.com/v1"
}
```

---

## 3. Integrating the Agent

To intercept and filter your target agent's outgoing LLM calls, point the agent at Sentinel's proxy instead of the real LLM endpoint.

For example, when using the standard OpenAI Python SDK, configure the base URL to target the `proxy_base_url` returned from the session creation step:

```python
import os
from openai import OpenAI

# Initialize client pointing at the Sentinel Intercept Proxy
client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",  # Replace with proxy_base_url
    api_key="mock-key-not-used"           # Handled by proxy session
)

# Outgoing requests are evaluated in real-time
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "My email is support@client.com"}]
)

print(response.choices[0].message.content)
```

---

## 4. Monitoring Intercept Sessions

### Get Live Counters & Status
Query active session statistics (processed, allowed, redacted, and blocked transactions):
```bash
curl "http://localhost:8000/api/v1/intercept/session/{session_id}/status"
```
**Example Response**:
```json
{
  "session_id": "caacf8aa-2036-4fb8-9aae-78b74bb1e456",
  "status": "running",
  "proxy_port": 8787,
  "proxy_base_url": "http://127.0.0.1:8787/v1",
  "transactions_processed": 5,
  "allowed_count": 3,
  "redacted_count": 1,
  "blocked_count": 1,
  "pii_types_encountered": ["email"],
  "ledger_path": "C:\\Users\\ADMIN\\Documents\\...\\transactions.jsonl"
}
```

### Tail the Forensic Ledger
Retrieve the last *N* audit entries recorded in the immutable log:
```bash
curl "http://localhost:8000/api/v1/intercept/session/{session_id}/ledger?n=50"
```
*Note: The returned logs contain message SHA-256 digests and type tags. No raw values or raw PII texts are persisted or shown.*

### Gracefully Shutdown Session
Shut down the proxy server and release the network port:
```bash
curl -X DELETE "http://localhost:8000/api/v1/intercept/session/{session_id}"
```

---

## 5. Running Verification Tests

To verify that the proxy infrastructure, API routing, and redaction engine are operating correctly, execute the automated integration test suite:

```bash
cd backend
uv run --extra dev pytest tests/test_api/test_intercept_routes.py
```
