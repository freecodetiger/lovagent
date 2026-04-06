#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_INDEX="${ROOT_DIR}/admin-ui/dist/index.html"
MODE="run"

while (($# > 0)); do
  case "$1" in
    --bootstrap)
      MODE="bootstrap"
      shift
      ;;
    --run)
      MODE="run"
      shift
      ;;
    --dev-ui)
      MODE="dev-ui"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
用法：
  scripts/check-env.sh --bootstrap
  scripts/check-env.sh --run
  scripts/check-env.sh --dev-ui

说明：
  --bootstrap  检查首次安装所需环境
  --run        检查默认启动所需环境
  --dev-ui     检查热更新前端开发所需环境
EOF
      exit 0
      ;;
    *)
      echo "未知参数：$1"
      exit 1
      ;;
  esac
done

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[OK] %s\n' "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[FAIL] %s\n' "$1"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

detect_os() {
  case "$(uname -s)" in
    Darwin)
      printf 'darwin\n'
      ;;
    Linux)
      printf 'linux\n'
      ;;
    *)
      printf 'other\n'
      ;;
  esac
}

has_apt() {
  command_exists apt-get
}

python_is_supported() {
  local candidate="$1"
  "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

python_has_venv() {
  local candidate="$1"
  "$candidate" - <<'PY' >/dev/null 2>&1
import ensurepip
import venv
raise SystemExit(0)
PY
}

choose_python() {
  local candidates=()
  if [[ -n "${LOVAGENT_PYTHON:-}" ]]; then
    candidates+=("${LOVAGENT_PYTHON}")
  fi
  candidates+=(python3.13 python3.12 python3.11 python3.10 python3)

  local candidate
  for candidate in "${candidates[@]}"; do
    if command_exists "$candidate" && python_is_supported "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

print_python_hint() {
  local os_name="$1"
  if [[ "${os_name}" == "darwin" ]]; then
    printf '  安装示例：brew install python@3.12\n'
    return
  fi

  if [[ "${os_name}" == "linux" ]] && has_apt; then
    printf '  安装示例：sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip\n'
    return
  fi

  printf '  请安装 Python 3.10+，并确保可用的 python3 带有 venv / ensurepip。\n'
}

print_node_hint() {
  local os_name="$1"
  if [[ "${os_name}" == "darwin" ]]; then
    printf '  安装示例：brew install node\n'
    return
  fi

  if [[ "${os_name}" == "linux" ]] && has_apt; then
    printf '  安装示例：sudo apt update && sudo apt install -y nodejs npm\n'
    return
  fi

  printf '  请安装 Node.js 18+ 与 npm。\n'
}

OS_NAME="$(detect_os)"

echo "LovAgent 环境检查模式：${MODE}"

if command_exists git; then
  pass "Git 可用：$(git --version | head -n 1)"
else
  fail "缺少 Git。"
fi

PYTHON_BIN="$(choose_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  fail "未找到可用的 Python 3.10+。"
  print_python_hint "${OS_NAME}"
else
  pass "Python 可用：$("${PYTHON_BIN}" --version 2>&1)"
  if python_has_venv "${PYTHON_BIN}"; then
    pass "Python 自带 venv / ensurepip，可创建虚拟环境。"
  else
    fail "检测到 ${PYTHON_BIN}，但缺少 venv / ensurepip。"
    print_python_hint "${OS_NAME}"
  fi
fi

NEED_NODE="false"
if [[ "${MODE}" == "bootstrap" || "${MODE}" == "dev-ui" || ! -f "${DIST_INDEX}" ]]; then
  NEED_NODE="true"
fi

if [[ "${NEED_NODE}" == "true" ]]; then
  if command_exists node && command_exists npm; then
    pass "Node.js 可用：$(node --version)"
    pass "npm 可用：$(npm --version)"
  else
    fail "缺少 Node.js 18+ 或 npm。"
    print_node_hint "${OS_NAME}"
  fi
else
  if command_exists node && command_exists npm; then
    pass "Node.js / npm 可用。"
  else
    warn "未检测到 Node.js / npm，但已存在 admin-ui/dist，默认启动仍可继续。"
  fi
fi

if command_exists curl; then
  pass "curl 可用。"
else
  warn "未检测到 curl，自动下载 cloudflared 与公网 IP 检查会受影响。"
fi

if command_exists cloudflared || [[ -x "${ROOT_DIR}/.tools/bin/cloudflared" ]]; then
  pass "cloudflared 可用。"
else
  warn "未检测到 cloudflared。可以先本地启动，但企业微信公网回调需要它或其他 HTTPS 暴露方式。"
fi

echo ""
echo "检查结果：${PASS_COUNT} 通过，${WARN_COUNT} 警告，${FAIL_COUNT} 失败"

if ((FAIL_COUNT > 0)); then
  exit 1
fi
