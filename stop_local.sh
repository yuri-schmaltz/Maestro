#!/usr/bin/env bash
# Para o backend Maestro iniciado por start_local.sh
#
# Uso:
#   ./stop_local.sh            # SIGTERM gracioso, fallback SIGKILL após 5s
#   ./stop_local.sh --force    # SIGKILL direto
#   ./stop_local.sh --clean    # também remove pidfile + log vazio

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$SCRIPT_DIR/app"
PIDFILE="$APP_DIR/.launcher.pid"

FORCE=0
CLEAN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --clean) CLEAN=1; shift ;;
    -h|--help)
      sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$PIDFILE" ]]; then
  echo "[stop_local] Sem pidfile — nada para parar"
  if [[ "$CLEAN" -eq 1 ]]; then
    rm -f "$APP_DIR/.launcher.log"
  fi
  exit 0
fi

PID=$(cat "$PIDFILE")
if ! kill -0 "$PID" 2>/dev/null; then
  echo "[stop_local] PID $PID já não está vivo — limpando pidfile stale"
  rm -f "$PIDFILE"
  exit 0
fi

echo "[stop_local] Matando backend PID $PID..."
if [[ "$FORCE" -eq 1 ]]; then
  kill -9 "$PID" 2>/dev/null || true
else
  kill "$PID" 2>/dev/null || true
  for i in 1 2 3 4 5; do
    if ! kill -0 "$PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if kill -0 "$PID" 2>/dev/null; then
    echo "[stop_local] SIGTERM não foi suficiente — SIGKILL"
    kill -9 "$PID" 2>/dev/null || true
  fi
fi

rm -f "$PIDFILE"
[[ "$CLEAN" -eq 1 ]] && rm -f "$APP_DIR/.launcher.log"

echo "[stop_local] OK — Maestro parado"
