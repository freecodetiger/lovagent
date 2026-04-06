#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"

kill_pid() {
  local pid="$1"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    sleep 1
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  fi
}

stop_pid_file() {
  local pid_file="$1"
  if [[ ! -f "${pid_file}" ]]; then
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  kill_pid "${pid}"

  rm -f "${pid_file}"
}

kill_matching_processes() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return
  fi

  local patterns=(
    "${ROOT_DIR}.+uvicorn app.main:app"
    "${ROOT_DIR}/admin-ui.+vite --host 0.0.0.0"
    "${ROOT_DIR}.+npm --prefix .+/admin-ui run dev"
  )

  local pattern
  local pid
  for pattern in "${patterns[@]}"; do
    while read -r pid; do
      [[ -n "${pid}" ]] || continue
      kill_pid "${pid}"
    done < <(pgrep -f "${pattern}" || true)
  done
}

stop_pid_file "${RUN_DIR}/frontend.pid"
stop_pid_file "${RUN_DIR}/backend.pid"
kill_matching_processes

echo "本地开发进程已停止。"
