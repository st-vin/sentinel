# No-Docker Setup Guide

Run Sentinel locally without Docker — works on **Windows**, macOS, and Linux.

---

## Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |
| npm | 9+ | Bundled with Node.js |
| Git | Any | https://git-scm.com/ |

> **Windows users**: Python and Node.js must be on your `PATH`. When installing Python on Windows, tick **"Add python.exe to PATH"** during setup. Use **PowerShell** (not CMD) for all commands below.

---

## Step 1 — Clone / Extract

**From ZIP**:
```powershell
# Windows PowerShell
Expand-Archive -Path sentinel.zip -DestinationPath .
cd sentinel
```

```bash
# macOS / Linux
unzip sentinel.zip && cd sentinel
```

---

## Step 2 — Configure Environment

```powershell
# Windows PowerShell
Copy-Item .env.example .env
notepad .env
```

```bash
# macOS / Linux
cp .env.example .env
nano .env   # or open with your editor
```

Minimum required in `.env` to run with mock data (no real credentials needed):
```env
ENVIRONMENT=development
STORAGE_BACKEND=local
```

Optional — add to enable real data sources:
```env
GOOGLE_API_KEY=your-gemini-api-key
ARIZE_API_KEY=your-arize-api-key
ARIZE_SPACE_KEY=your-arize-space-key
ELASTIC_API_KEY=your-elastic-api-key
ELASTIC_CLOUD_ID=your-elastic-cloud-id
```

---

## Step 3 — Backend Setup

### Windows PowerShell
```powershell
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# If you get an execution policy error, run first:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -e .
```

### macOS / Linux
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Note on WeasyPrint (PDF generation)**:  
> WeasyPrint requires GTK/Pango libraries. On Windows, the easiest path is:
> ```powershell
> pip install weasyprint
> # If it fails on Windows, install the GTK3 runtime from:
> # https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
> ```
> If WeasyPrint cannot be installed, Sentinel automatically falls back to returning HTML instead of PDF — all other features work normally.

---

## Step 4 — Start the Backend

```powershell
# Windows — inside backend/ with venv activated
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# macOS / Linux
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test it: open http://localhost:8000/health in your browser.

---

## Step 5 — Start the Mock Target Agent (optional but recommended)

Open a **second terminal**:

### Windows PowerShell
```powershell
cd mock_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic
uvicorn main:app --host 0.0.0.0 --port 8001
```

### macOS / Linux
```bash
cd mock_agent
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic
uvicorn main:app --host 0.0.0.0 --port 8001
```

The mock agent is the built-in vulnerable demo target. When you run an audit against `http://localhost:8001/chat`, Sentinel will detect prompt injection, PII leakage, and hallucination findings.

---

## Step 6 — Frontend Setup

Open a **third terminal**:

```powershell
# Windows
cd frontend
npm install
npm run dev
```

```bash
# macOS / Linux
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

---

## Step 7 — Run Your First Audit

1. Open http://localhost:3000
2. **Target Agent Endpoint**: `http://localhost:8001/chat`
3. Leave Arize/Elastic fields empty (mock data will be used)
4. Select all three compliance modules
5. Click **RUN AUDIT**
6. Watch the live dashboard — results appear in ~60 seconds

---

## Running Tests

```powershell
# Windows — from backend/ with venv activated
pytest --tb=short -q
```

```bash
# macOS / Linux
cd backend && pytest --tb=short -q
```

---

## Running the Evaluation Suite

```powershell
# Windows — from backend/ with venv activated
python -m eval.runner
```

```bash
# macOS / Linux
cd backend && python -m eval.runner
```

---

## Troubleshooting

### "uvicorn: command not found" (Windows)
```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### "CORS error" in browser
Ensure the backend is running on port 8000 and the frontend is on port 3000. The backend is configured to allow all origins in development.

### "WeasyPrint failed" / PDF downloads show HTML
This is expected on Windows without the GTK runtime. The JSON export still works. To fix, install GTK3: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

### Port already in use
```powershell
# Windows — find and kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

```bash
# macOS / Linux
lsof -ti:8000 | xargs kill -9
```

### Python "No module named ..." after installing
Make sure your virtual environment is activated. You should see `(.venv)` in your prompt.

---

## Quick-Reference: All Commands

| Task | Windows PowerShell | macOS / Linux |
|------|-------------------|---------------|
| Activate venv (backend) | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Start backend | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` | same |
| Start mock agent | `uvicorn main:app --host 0.0.0.0 --port 8001` | same |
| Start frontend | `npm run dev` | same |
| Run tests | `pytest --tb=short -q` | same |
| Run evals | `python -m eval.runner` | same |
| Deactivate venv | `deactivate` | same |
