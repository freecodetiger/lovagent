#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_SCRIPT="${ROOT_DIR}/scripts/check-env.sh"
TOOLS_DIR="${ROOT_DIR}/.tools/bin"
VENV_DIR="${ROOT_DIR}/.venv"
ADMIN_DIR="${ROOT_DIR}/admin-ui"
DIST_INDEX="${ADMIN_DIR}/dist/index.html"

mkdir -p "${TOOLS_DIR}"

"${CHECK_SCRIPT}" --bootstrap

log() {
  printf '%s\n' "$1"
}

warn() {
  printf 'Warning: %s\n' "$1"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

python_is_supported() {
  local candidate="$1"
  "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
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

ensure_supported_venv() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    return 1
  fi

  if ! python_is_supported "${VENV_DIR}/bin/python"; then
    warn "检测到现有 .venv 使用的 Python 版本低于 3.10，正在重建虚拟环境。"
    rm -rf "${VENV_DIR}"
    return 1
  fi

  return 0
}

install_python_dependencies() {
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"
}

build_admin_ui() {
  if ! command_exists npm; then
    if [[ -f "${DIST_INDEX}" ]]; then
      warn "未检测到 npm，跳过前端构建，继续使用已有 dist。"
      return 0
    fi
    log "缺少 npm。请先安装 Node.js 18+，再重新运行 scripts/bootstrap.sh。"
    return 1
  fi

  if [[ -f "${ADMIN_DIR}/package-lock.json" ]]; then
    npm --prefix "${ADMIN_DIR}" ci
  else
    npm --prefix "${ADMIN_DIR}" install
  fi

  npm --prefix "${ADMIN_DIR}" run build
}

download_cloudflared() {
  if command_exists cloudflared || [[ -x "${TOOLS_DIR}/cloudflared" ]]; then
    return 0
  fi

  if ! command_exists curl; then
    warn "未检测到 curl，跳过 cloudflared 下载。需要公网回调时请手动安装 cloudflared。"
    return 0
  fi

  local os_name
  local arch_name
  os_name="$(uname -s)"
  arch_name="$(uname -m)"

  case "${arch_name}" in
    x86_64|amd64)
      arch_name="amd64"
      ;;
    arm64|aarch64)
      arch_name="arm64"
      ;;
    *)
      warn "暂不支持自动下载 cloudflared：未知架构 ${arch_name}。"
      return 0
      ;;
  esac

  case "${os_name}" in
    Linux)
      curl -fsSL \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch_name}" \
        -o "${TOOLS_DIR}/cloudflared"
      chmod +x "${TOOLS_DIR}/cloudflared"
      ;;
    Darwin)
      local archive
      local temp_dir
      temp_dir="$(mktemp -d)"
      archive="${temp_dir}/cloudflared.tgz"
      curl -fsSL \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-${arch_name}.tgz" \
        -o "${archive}"
      tar -xzf "${archive}" -C "${temp_dir}"
      mv "${temp_dir}/cloudflared" "${TOOLS_DIR}/cloudflared"
      chmod +x "${TOOLS_DIR}/cloudflared"
      rm -rf "${temp_dir}"
      ;;
    *)
      warn "当前系统 ${os_name} 不支持自动下载 cloudflared，请手动安装。"
      ;;
  esac
}

if ! ensure_supported_venv; then
  PYTHON_BIN="$(choose_python || true)"
  if [[ -z "${PYTHON_BIN:-}" ]]; then
    log "未找到可用的 Python 3.10+。"
    log "请先安装 Python 3.10 或更高版本，再重新运行 scripts/bootstrap.sh。"
    exit 1
  fi

  log "使用 ${PYTHON_BIN} 创建虚拟环境。"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

install_python_dependencies
build_admin_ui
download_cloudflared

log ""
log "Bootstrap 完成。"
log ""
log "已准备好的依赖："
log "- Python 虚拟环境：${VENV_DIR}"
log "- 管理前端构建产物：${DIST_INDEX}"
if command_exists cloudflared || [[ -x "${TOOLS_DIR}/cloudflared" ]]; then
  log "- cloudflared：可用"
else
  log "- cloudflared：未安装（仅企业微信公网回调需要）"
fi
log ""
log "下一步："
log "1. 运行 scripts/dev-up.sh"
log "2. 打开 http://127.0.0.1:8000/setup"
log "3. 在网页向导里填写 GLM、企业微信和管理员密码"
log ""
log "如需前端热更新开发，再运行：scripts/dev-up.sh --dev-ui"
