#!/bin/bash
set -Eeuo pipefail

PID_DIR=/var/run/snmpsim
mkdir -p "$PID_DIR"
rm -f "${PID_DIR}/snmptrapd.pid" "${PID_DIR}/snmpsim.pid"

START_TRAP=1
case "${SNMPTRAPD_ENABLED:-1}" in
  0|false|False|FALSE)
    echo "snmptrapd disabled via SNMPTRAPD_ENABLED=${SNMPTRAPD_ENABLED}"
    START_TRAP=0
    ;;
  *)
    echo "snmptrapd enabled (set SNMPTRAPD_ENABLED=0 to disable)"
    ;;
esac

if [ "$START_TRAP" -eq 1 ]; then
  echo "Starting PySNMP snmptrapd helper on ${SNMPTRAPD_ADDRESS:-0.0.0.0}:${SNMPTRAPD_PORT:-162}"
  python3 /opt/snmptrapd.py &
  SNMPTRAPD_PID=$!
  echo "$SNMPTRAPD_PID" > "${PID_DIR}/snmptrapd.pid"
fi

EXTRA_FLAGS_VALUE="${EXTRA_FLAGS:-}"
if [ -n "$EXTRA_FLAGS_VALUE" ]; then
  read -r -a EXTRA_ARGS <<< "$EXTRA_FLAGS_VALUE"
else
  EXTRA_ARGS=()
fi

export SNMPSIM_ALLOW_ROOT=true
echo "Starting snmpsim-command-responder on 0.0.0.0:161"
snmpsim-command-responder --agent-udpv4-endpoint=0.0.0.0:161 "${EXTRA_ARGS[@]}" &
SNMPSIM_PID=$!
echo "$SNMPSIM_PID" > "${PID_DIR}/snmpsim.pid"

cleanup() {
  echo "Stopping snmpsim services..."
  if [ "$START_TRAP" -eq 1 ]; then
    if kill -0 "$SNMPTRAPD_PID" 2>/dev/null; then
      kill -TERM "$SNMPTRAPD_PID" 2>/dev/null || true
    fi
  fi
  if kill -0 "$SNMPSIM_PID" 2>/dev/null; then
    kill -TERM "$SNMPSIM_PID" 2>/dev/null || true
  fi
  rm -f "${PID_DIR}/snmptrapd.pid" "${PID_DIR}/snmpsim.pid"
}
trap cleanup SIGTERM SIGINT

if [ "$START_TRAP" -eq 1 ]; then
  wait -n "$SNMPTRAPD_PID" "$SNMPSIM_PID"
  wait "$SNMPTRAPD_PID" 2>/dev/null || true
  wait "$SNMPSIM_PID" 2>/dev/null || true
else
  wait "$SNMPSIM_PID" 2>/dev/null || true
fi
