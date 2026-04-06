#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
ADMIN_DIR="${ROOT_DIR}/admin-ui"
DIST_INDEX="${ADMIN_DIR}/dist/index.html"

ENABLE_DEV_UI="false"

while (($# > 0)); do
  case "$1" in
    --dev-ui)
      ENABLE_DEV_UI="true"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
用法：
  scripts/dev-up.sh
  scripts/dev-up.sh --dev-ui

默认行为：
  只启动后端 http://127.0.0.1:8000，并直接复用已构建的 admin-ui/dist。

可选参数：
  --dev-ui    额外启动 Vite 开发服务器 http://127.0.0.1:5173
EOF
      exit 0
      ;;
    *)
      echo "未知参数：$1"
      exit 1
      ;;
  esac
done

mkdir -p "${RUN_DIR}"
cd "${ROOT_DIR}"

cleanup_stale_pid() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]] && ! kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    rm -f "${pid_file}"
  fi
}

cleanup_stale_pid "${RUN_DIR}/backend.pid"
cleanup_stale_pid "${RUN_DIR}/frontend.pid"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "缺少 .venv，请先执行 scripts/bootstrap.sh"
  exit 1
fi

if ! "${VENV_PYTHON}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "当前 .venv 使用的 Python 版本低于 3.10，请重新执行 scripts/bootstrap.sh"
  exit 1
fi

if [[ ! -f "${DIST_INDEX}" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "缺少 admin-ui/dist，且未检测到 npm。请先安装 Node.js 18+ 并执行 scripts/bootstrap.sh"
    exit 1
  fi
  npm --prefix "${ADMIN_DIR}" run build
fi

if [[ -f "${RUN_DIR}/backend.pid" ]] && kill -0 "$(cat "${RUN_DIR}/backend.pid")" 2>/dev/null; then
  echo "后端已经在运行。"
  exit 1
fi

if [[ "${ENABLE_DEV_UI}" == "true" ]] && [[ -f "${RUN_DIR}/frontend.pid" ]] && kill -0 "$(cat "${RUN_DIR}/frontend.pid")" 2>/dev/null; then
  echo "前端开发服务器已经在运行。"
  exit 1
fi

nohup bash -lc "cd '${ROOT_DIR}' && exec '${VENV_PYTHON}' -m uvicorn app.main:app --host 0.0.0.0 --port 8000" \
  </dev/null > "${RUN_DIR}/backend.log" 2>&1 &
echo $! > "${RUN_DIR}/backend.pid"

if [[ "${ENABLE_DEV_UI}" == "true" ]]; then
  nohup bash -lc "cd '${ROOT_DIR}' && exec npm --prefix '${ADMIN_DIR}' run dev -- --host 0.0.0.0" \
    </dev/null > "${RUN_DIR}/frontend.log" 2>&1 &
  echo $! > "${RUN_DIR}/frontend.pid"
fi

sleep 2

if ! kill -0 "$(cat "${RUN_DIR}/backend.pid")" 2>/dev/null; then
  echo "后端启动失败，请检查 ${RUN_DIR}/backend.log"
  exit 1
fi

if [[ "${ENABLE_DEV_UI}" == "true" ]] && ! kill -0 "$(cat "${RUN_DIR}/frontend.pid")" 2>/dev/null; then
  echo "前端启动失败，请检查 ${RUN_DIR}/frontend.log"
  exit 1
fi

cat <<EOF
开发环境已启动。

- Setup Wizard: http://127.0.0.1:8000/setup
- Admin UI: http://127.0.0.1:8000/admin
- Backend API: http://127.0.0.1:8000
EOF

if [[ "${ENABLE_DEV_UI}" == "true" ]]; then
  cat <<EOF
- Vite Dev UI: http://127.0.0.1:5173
EOF
fi

cat <<EOF

日志：
- ${RUN_DIR}/backend.log
EOF

if [[ "${ENABLE_DEV_UI}" == "true" ]]; then
  cat <<EOF
- ${RUN_DIR}/frontend.log
EOF
fi
