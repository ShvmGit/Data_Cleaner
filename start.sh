#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  DataCleaner AI — Project Startup Script
#  Usage:  bash start.sh          (starts both backend + frontend)
#          bash start.sh backend  (backend only)
#          bash start.sh frontend (frontend only)
#          bash start.sh install  (install all dependencies)
#          bash start.sh stop     (kill running servers)
# ──────────────────────────────────────────────────────────────

set -e

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Project root (where this script lives) ──
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# ── Helpers ──
banner() {
  echo ""
  echo -e "${PURPLE}${BOLD}  ✨ DataCleaner AI${NC}"
  echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "  AI-Powered Data Cleaning & EDA Pipeline"
  echo -e "${CYAN}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

log_info()    { echo -e "  ${BLUE}ℹ${NC}  $1"; }
log_success() { echo -e "  ${GREEN}✔${NC}  $1"; }
log_warn()    { echo -e "  ${YELLOW}⚠${NC}  $1"; }
log_error()   { echo -e "  ${RED}✖${NC}  $1"; }
log_step()    { echo -e "\n  ${BOLD}${CYAN}▶ $1${NC}"; }

# ── Check prerequisites ──
check_prereqs() {
  log_step "Checking prerequisites..."

  # Python
  if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
  elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
  else
    log_error "Python 3.11+ is required but not found."
    log_info  "Install from: https://python.org/downloads"
    exit 1
  fi

  PY_VERSION=$($PYTHON_CMD --version 2>&1 | grep -oP '\d+\.\d+')
  log_success "Python $PY_VERSION found ($PYTHON_CMD)"

  # Node.js
  if ! command -v node &>/dev/null; then
    log_error "Node.js 18+ is required but not found."
    log_info  "Install from: https://nodejs.org"
    exit 1
  fi

  NODE_VERSION=$(node --version)
  log_success "Node.js $NODE_VERSION found"

  # npm
  if ! command -v npm &>/dev/null; then
    log_error "npm is required but not found."
    exit 1
  fi
  log_success "npm $(npm --version) found"
}

# ── Check .env ──
check_env() {
  log_step "Checking environment..."

  if [ ! -f "$BACKEND_DIR/.env" ]; then
    if [ -f "$BACKEND_DIR/.env.example" ]; then
      cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
      log_warn "Created backend/.env from .env.example"
      log_warn "${YELLOW}→ Please add your GROQ_API_KEY to backend/.env${NC}"
    else
      log_error "No .env or .env.example found in backend/"
      exit 1
    fi
  else
    # Check if GROQ_API_KEY is set
    if grep -q "GROQ_API_KEY=your_" "$BACKEND_DIR/.env" 2>/dev/null || \
       grep -q "GROQ_API_KEY=$" "$BACKEND_DIR/.env" 2>/dev/null; then
      log_warn "${YELLOW}GROQ_API_KEY is not configured in backend/.env${NC}"
      log_warn "The pipeline will use fallback mode without a valid API key."
    else
      log_success "backend/.env configured"
    fi
  fi
}

# ── Install dependencies ──
install_deps() {
  log_step "Installing backend dependencies..."
  cd "$BACKEND_DIR"

  # Create virtual environment if it doesn't exist
  if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv venv
    log_success "Created Python virtual environment"
  fi

  # Activate venv
  if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
  elif [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
  fi

  pip install -r requirements.txt --quiet
  log_success "Backend dependencies installed"

  log_step "Installing frontend dependencies..."
  cd "$FRONTEND_DIR"
  npm install --silent
  log_success "Frontend dependencies installed"

  cd "$PROJECT_ROOT"
}

# ── Start backend ──
start_backend() {
  log_step "Starting backend (FastAPI on port $BACKEND_PORT)..."
  cd "$BACKEND_DIR"

  # Activate venv if exists
  if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
  elif [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
  fi

  # Kill existing process on the port
  if lsof -i :$BACKEND_PORT &>/dev/null 2>&1; then
    log_warn "Port $BACKEND_PORT in use — killing existing process..."
    kill $(lsof -t -i :$BACKEND_PORT) 2>/dev/null || true
    sleep 1
  fi

  # Start uvicorn in background
  $PYTHON_CMD -m uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$PROJECT_ROOT/.backend.pid"

  # Wait for health check
  sleep 3
  if curl -s "http://localhost:$BACKEND_PORT/api/health" &>/dev/null; then
    log_success "Backend running → ${BOLD}http://localhost:$BACKEND_PORT${NC}"
    log_success "API docs      → ${BOLD}http://localhost:$BACKEND_PORT/docs${NC}"
  else
    log_warn "Backend starting (may take a few seconds)..."
    log_info "Backend PID: $BACKEND_PID"
  fi

  cd "$PROJECT_ROOT"
}

# ── Start frontend ──
start_frontend() {
  log_step "Starting frontend (Next.js on port $FRONTEND_PORT)..."
  cd "$FRONTEND_DIR"

  # Kill existing process on the port
  if lsof -i :$FRONTEND_PORT &>/dev/null 2>&1; then
    log_warn "Port $FRONTEND_PORT in use — killing existing process..."
    kill $(lsof -t -i :$FRONTEND_PORT) 2>/dev/null || true
    sleep 1
  fi

  npm run dev &
  FRONTEND_PID=$!
  echo $FRONTEND_PID > "$PROJECT_ROOT/.frontend.pid"

  sleep 3
  log_success "Frontend running → ${BOLD}http://localhost:$FRONTEND_PORT${NC}"

  cd "$PROJECT_ROOT"
}

# ── Stop servers ──
stop_servers() {
  log_step "Stopping servers..."

  if [ -f "$PROJECT_ROOT/.backend.pid" ]; then
    BPID=$(cat "$PROJECT_ROOT/.backend.pid")
    kill $BPID 2>/dev/null && log_success "Backend stopped (PID: $BPID)" || log_warn "Backend was not running"
    rm "$PROJECT_ROOT/.backend.pid"
  fi

  if [ -f "$PROJECT_ROOT/.frontend.pid" ]; then
    FPID=$(cat "$PROJECT_ROOT/.frontend.pid")
    kill $FPID 2>/dev/null && log_success "Frontend stopped (PID: $FPID)" || log_warn "Frontend was not running"
    rm "$PROJECT_ROOT/.frontend.pid"
  fi

  # Also kill by port as fallback
  if command -v lsof &>/dev/null; then
    kill $(lsof -t -i :$BACKEND_PORT) 2>/dev/null || true
    kill $(lsof -t -i :$FRONTEND_PORT) 2>/dev/null || true
  fi

  log_success "All servers stopped"
}

# ── Main ──
main() {
  banner

  case "${1:-all}" in
    install)
      check_prereqs
      install_deps
      check_env
      echo ""
      log_success "${GREEN}${BOLD}All dependencies installed!${NC}"
      log_info "Run ${BOLD}bash start.sh${NC} to start the project."
      ;;

    backend)
      check_prereqs
      check_env
      start_backend
      echo ""
      log_success "${GREEN}${BOLD}Backend is running!${NC}"
      echo -e "  Press ${BOLD}Ctrl+C${NC} to stop.\n"
      wait
      ;;

    frontend)
      start_frontend
      echo ""
      log_success "${GREEN}${BOLD}Frontend is running!${NC}"
      echo -e "  Press ${BOLD}Ctrl+C${NC} to stop.\n"
      wait
      ;;

    stop)
      stop_servers
      ;;

    all|start)
      check_prereqs
      check_env

      # Auto-install if node_modules or venv missing
      if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_warn "node_modules not found — installing..."
        install_deps
      fi

      start_backend
      start_frontend

      echo ""
      echo -e "  ${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
      echo -e "  ${GREEN}${BOLD}  🚀 DataCleaner AI is ready!${NC}"
      echo -e "  ${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
      echo ""
      echo -e "  ${BOLD}Frontend${NC}  → http://localhost:$FRONTEND_PORT"
      echo -e "  ${BOLD}Backend${NC}   → http://localhost:$BACKEND_PORT"
      echo -e "  ${BOLD}API Docs${NC}  → http://localhost:$BACKEND_PORT/docs"
      echo ""
      echo -e "  Press ${BOLD}Ctrl+C${NC} to stop both servers."
      echo ""

      # Handle Ctrl+C gracefully
      trap 'echo ""; log_step "Shutting down..."; stop_servers; exit 0' INT TERM
      wait
      ;;

    *)
      echo "Usage: bash start.sh [command]"
      echo ""
      echo "Commands:"
      echo "  install    Install all dependencies (pip + npm)"
      echo "  backend    Start backend only"
      echo "  frontend   Start frontend only"
      echo "  stop       Stop all running servers"
      echo "  start/all  Start both (default)"
      echo ""
      ;;
  esac
}

main "$@"
