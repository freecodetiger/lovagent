#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"

mkdir -p "${RUN_DIR}"
cd "${ROOT_DIR}"

if [[ ! -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  echo "缺少 .venv，请先执行 scripts/bootstrap.sh"
  exit 1
fi

if [[ -f "${RUN_DIR}/backend.pid" ]] && kill -0 "$(cat "${RUN_DIR}/backend.pid")" 2>/dev/null; then
  echo "后端已经在运行。"
  exit 1
fi

if [[ -f "${RUN_DIR}/frontend.pid" ]] && kill -0 "$(cat "${RUN_DIR}/frontend.pid")" 2>/dev/null; then
  echo "前端已经在运行。"
  exit 1
fi

nohup bash -lc "cd '${ROOT_DIR}' && exec '${ROOT_DIR}/.venv/bin/python' -m uvicorn app.main:app --host 0.0.0.0 --port 8000" \
  </dev/null > "${RUN_DIR}/backend.log" 2>&1 &
echo $! > "${RUN_DIR}/backend.pid"

nohup bash -lc "cd '${ROOT_DIR}' && exec npm --prefix '${ROOT_DIR}/admin-ui' run dev -- --host 0.0.0.0" \
  </dev/null > "${RUN_DIR}/frontend.log" 2>&1 &
echo $! > "${RUN_DIR}/frontend.pid"

sleep 2

if ! kill -0 "$(cat "${RUN_DIR}/backend.pid")" 2>/dev/null; then
  echo "后端启动失败，请检查 ${RUN_DIR}/backend.log"
  exit 1
fi

if ! kill -0 "$(cat "${RUN_DIR}/frontend.pid")" 2>/dev/null; then
  echo "前端启动失败，请检查 ${RUN_DIR}/frontend.log"
  exit 1
fi

cat <<EOF
开发环境已启动。

- Setup Wizard: http://127.0.0.1:8000/setup
- Admin UI (Vite): http://127.0.0.1:5173
- Backend API: http://127.0.0.1:8000

日志：
- ${RUN_DIR}/backend.log
- ${RUN_DIR}/frontend.log
EOF
