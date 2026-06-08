#!/usr/bin/env bash
# Sentinel — macOS / Linux Setup Script
# Run from the sentinel/ directory: bash setup.sh

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}===============================================${NC}"
echo -e "${CYAN}  Sentinel AI GRC Auditor — Unix Setup        ${NC}"
echo -e "${CYAN}===============================================${NC}"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[ERROR] python3 not found. Install Python 3.11+ first.${NC}"
    exit 1
fi
PY_VERSION=$(python3 --version)
echo -e "${GREEN}[OK] $PY_VERSION${NC}"

# Check Node
if ! command -v node &>/dev/null; then
    echo -e "${RED}[ERROR] node not found. Install Node.js 18+ from https://nodejs.org/${NC}"
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "${GREEN}[OK] Node.js $NODE_VERSION${NC}"

# Copy .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}[OK] Created .env from .env.example — edit it to add your credentials${NC}"
else
    echo -e "${GREEN}[OK] .env already exists${NC}"
fi

# Backend
echo ""
echo -e "${CYAN}Setting up backend...${NC}"
cd backend
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -e . -q
echo -e "${GREEN}[OK] Backend dependencies installed${NC}"
deactivate
cd ..

# Mock agent
echo ""
echo -e "${CYAN}Setting up mock agent...${NC}"
cd mock_agent
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install fastapi uvicorn pydantic -q
echo -e "${GREEN}[OK] Mock agent dependencies installed${NC}"
deactivate
cd ..

# Frontend
echo ""
echo -e "${CYAN}Setting up frontend...${NC}"
cd frontend
npm install --silent
echo -e "${GREEN}[OK] Frontend dependencies installed${NC}"
cd ..

echo ""
echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}===============================================${NC}"
echo ""
echo "Open 3 terminal tabs:"
echo ""
echo -e "${YELLOW}Tab 1 — Backend:${NC}"
echo "  cd backend && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo -e "${YELLOW}Tab 2 — Mock Agent:${NC}"
echo "  cd mock_agent && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8001"
echo ""
echo -e "${YELLOW}Tab 3 — Frontend:${NC}"
echo "  cd frontend && npm run dev"
echo ""
echo -e "${CYAN}Then open http://localhost:3000 in your browser.${NC}"
echo ""
