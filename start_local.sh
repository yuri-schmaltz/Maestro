#!/usr/bin/env bash
# Maestro — launcher local standalone
#
# Sobe o backend FastAPI/Uvicorn direto, usando o venv já criado em app/env/.
#
# Uso:
#   ./start_local.sh                  # porta padrão 7860, log em .launcher.log
#   ./start_local.sh --port 7865      # porta custom
#   ./start_local.sh --compile        # passa --compile para launch.py (kernel fusion)
#   ./start_local.sh --share          # liga 0.0.0.0 (LAN) em vez de 127.0.0.1
#   ./start_local.sh --no-build       # pula verificação de UI build

set -euo pipefail

# Resolve diretório do script (funciona com symlinks)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$SCRIPT_DIR/app"
PIDFILE="$APP_DIR/.launcher.pid"
LOGFILE="$APP_DIR/.launcher.log"

# Defaults
PORT="7860"
COMPILE_FLAG=""
BIND_HOST="127.0.0.1"
SKIP_BUILD=0

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port|-p)
      if [[ $# -lt 2 || ! "$2" =~ ^[0-9]{1,5}$ ]]; then
        echo "[start_local] ERRO: --port requer um número entre 1 e 65535" >&2
        exit 2
      fi
      PORT=$((10#$2))
      if (( PORT < 1 || PORT > 65535 )); then
        echo "[start_local] ERRO: porta deve estar entre 1 e 65535" >&2
        exit 2
      fi
      shift 2 ;;
    --compile)     COMPILE_FLAG="--compile"; shift ;;
    --share)       BIND_HOST="0.0.0.0"; shift ;;
    --no-build)    SKIP_BUILD=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "Argumento desconhecido: $1" >&2
      exit 2 ;;
  esac
done

echo "[start_local] Maestro launcher (standalone) — porta $PORT ($BIND_HOST)"

# --- 1. Detect venv ---
VENV=""
for candidate in env-sol env-rtx50 env; do
  if [[ -x "$APP_DIR/$candidate/bin/python" ]]; then
    VENV="$candidate"
    break
  fi
done

if [[ -z "$VENV" ]]; then
  echo "[start_local] ERRO: nenhum venv encontrado em app/env{,-sol,-rtx50}/" >&2
  echo "             Crie o ambiente Python conforme README.md:" >&2
  exit 1
fi
PY="$APP_DIR/$VENV/bin/python"
echo "[start_local] Usando venv: $VENV ($PY)"

# --- 2. Sanity: GPU detectável ---
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || true)
  GPU_DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || true)
  echo "[start_local] GPU: ${GPU_NAME:-desconhecida} (driver ${GPU_DRIVER:-?})"
else
  echo "[start_local] AVISO: nvidia-smi não encontrado — verifique o driver NVIDIA antes de gerar mídia"
fi

# --- 3. Sanity: UI buildada ---
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  if [[ ! -f "$SCRIPT_DIR/ui/dist/index.html" ]]; then
    echo "[start_local] UI não buildada — correndo npm install + npm run build..."
    if [[ ! -d "$SCRIPT_DIR/ui/node_modules" ]]; then
      (cd "$SCRIPT_DIR/ui" && npm install) || {
        echo "[start_local] ERRO: npm install falhou" >&2
        exit 3
      }
    fi
    (cd "$SCRIPT_DIR/ui" && npm run build) || {
      echo "[start_local] ERRO: UI build falhou" >&2
      exit 3
    }
  else
    echo "[start_local] UI dist já existe — ok"
  fi
fi

# --- 4. Se já tem lock, mata anterior ---
if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null || true)
  if [[ -n "${OLD_PID:-}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[start_local] PID $OLD_PID ainda vivo — matando..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 2
    kill -9 "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
fi

# --- 5. Limpa qualquer holder fantasma da porta ---
if command -v ss >/dev/null 2>&1; then
  HOLDER=$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $0}' | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  if [[ -n "${HOLDER:-}" ]]; then
    echo "[start_local] Porta $PORT ocupada por PID $HOLDER — matando"
    kill "$HOLDER" 2>/dev/null || true
    sleep 2
    kill -9 "$HOLDER" 2>/dev/null || true
  fi
fi

# --- 6. Sobe o backend ---
cd "$APP_DIR"
echo "[start_local] Lançando backend → log: $LOGFILE"
SERVER_NAME="$BIND_HOST" SERVER_PORT="$PORT" \
  nohup "$PY" launch.py $COMPILE_FLAG >"$LOGFILE" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PIDFILE"

echo "[start_local] Backend PID: $BACKEND_PID"

# --- 7. Espera o bind aparecer ---
URL="http://127.0.0.1:${PORT}/"
echo -n "[start_local] Aguardando bind em ${BIND_HOST}:${PORT} "
WAITED=0
MAX_WAIT=120
while (( WAITED < MAX_WAIT )); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo ""
    echo "[start_local] ERRO: backend morreu logo após o start. Últimas linhas do log:" >&2
    tail -40 "$LOGFILE" >&2
    rm -f "$PIDFILE"
    exit 4
  fi
  if curl --noproxy '*' --fail -sS -o /dev/null --max-time 1 "$URL" 2>/dev/null; then
    echo " OK (após ${WAITED}s)"
    break
  fi
  echo -n "."
  sleep 1
  WAITED=$(( WAITED + 1 ))
done

if (( WAITED >= MAX_WAIT )); then
  echo ""
  echo "[start_local] ERRO: backend não respondeu em ${MAX_WAIT}s. Tail do log:" >&2
  tail -40 "$LOGFILE" >&2
  echo "[start_local] PID $BACKEND_PID ainda vivo — matando" >&2
  kill "$BACKEND_PID" 2>/dev/null || true
  rm -f "$PIDFILE"
  exit 5
fi

# --- 8. Resumo ---
echo ""
echo "============================================================"
echo "  Maestro está rodando!"
echo ""
echo "  UI (React):  $URL"
echo "  UI clássica: ${URL}classic/"
echo "  API docs:    ${URL}docs"
echo ""
echo "  PID:   $BACKEND_PID  (pidfile: $PIDFILE)"
echo "  Log:   $LOGFILE"
echo ""
echo "  Pare com:  ./stop_local.sh"
echo "  Acompanhe: tail -f $LOGFILE"
echo "============================================================"
