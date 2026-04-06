#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${ROOT_DIR}/.tools/bin"

mkdir -p "${TOOLS_DIR}"

if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
  python3 -m venv "${ROOT_DIR}/.venv"
fi

"${ROOT_DIR}/.venv/bin/pip" install --upgrade pip
"${ROOT_DIR}/.venv/bin/pip" install -r "${ROOT_DIR}/requirements.txt"

npm --prefix "${ROOT_DIR}/admin-ui" ci

if ! command -v cloudflared >/dev/null 2>&1 && [[ ! -x "${TOOLS_DIR}/cloudflared" ]]; then
  case "$(uname -m)" in
    x86_64|amd64)
      cloudflared_arch="amd64"
      ;;
    aarch64|arm64)
      cloudflared_arch="arm64"
      ;;
    *)
      cloudflared_arch=""
      ;;
  esac

  if [[ -n "${cloudflared_arch}" ]]; then
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${cloudflared_arch}" \
      -o "${TOOLS_DIR}/cloudflared"
    chmod +x "${TOOLS_DIR}/cloudflared"
  else
    printf '跳过 cloudflared 下载：当前架构 %s 未内置支持。\n' "$(uname -m)"
  fi
fi

cat <<EOF
Bootstrap 完成。

下一步：
1. 运行 scripts/dev-up.sh
2. 打开 http://127.0.0.1:8000/setup
3. 在网页向导里填写 GLM、企业微信和管理员密码
EOF
