FROM node:20-bookworm-slim AS ui-builder

WORKDIR /build/admin-ui

COPY admin-ui/package.json admin-ui/package-lock.json ./
RUN npm ci

COPY admin-ui/index.html ./
COPY admin-ui/tsconfig.json ./
COPY admin-ui/tsconfig.app.json ./
COPY admin-ui/vite.config.ts ./
COPY admin-ui/src ./src

RUN npm run build


FROM python:3.12-slim

ARG TARGETARCH

ENV PYTHONUNBUFFERED=1 \
    DATABASE_TYPE=sqlite \
    DATABASE_PATH=/data/girlchat.db \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN case "${TARGETARCH}" in \
      "amd64") cloudflared_arch="amd64" ;; \
      "arm64") cloudflared_arch="arm64" ;; \
      *) echo "Unsupported TARGETARCH: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${cloudflared_arch}" -o /usr/local/bin/cloudflared \
    && chmod +x /usr/local/bin/cloudflared

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY --from=ui-builder /build/admin-ui/dist ./admin-ui/dist

RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
