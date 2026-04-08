"""
临时公网媒体文件托管。
"""

from __future__ import annotations

from pathlib import Path
import secrets
from typing import Optional

from app.services.runtime_config_service import runtime_config_service
from app.services.tunnel_service import tunnel_service


BASE_DIR = Path(__file__).resolve().parent.parent.parent
PUBLIC_MEDIA_DIR = BASE_DIR / ".runtime" / "media-temp"
PUBLIC_MEDIA_ROUTE = "/media-temp"


class PublicMediaService:
    """将临时媒体文件保存到本地，并生成可被外部模型访问的 HTTPS URL。"""

    def __init__(self) -> None:
        PUBLIC_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    def ensure_directory(self) -> Path:
        PUBLIC_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        return PUBLIC_MEDIA_DIR

    def resolve_public_base_url(self) -> str:
        configured = runtime_config_service.get_effective_public_base_url().strip().rstrip("/")
        if configured:
            return configured

        tunnel_service.ensure_started()
        return str((tunnel_service.get_status() or {}).get("public_url") or "").strip().rstrip("/")

    def save_binary(self, content: bytes, suffix: str) -> str:
        directory = self.ensure_directory()
        cleaned_suffix = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ""
        filename = f"{secrets.token_hex(16)}{cleaned_suffix}"
        target = directory / filename
        target.write_bytes(content)
        return filename

    def build_public_url(self, filename: str) -> Optional[str]:
        public_base_url = self.resolve_public_base_url()
        if not public_base_url:
            return None
        return f"{public_base_url}{PUBLIC_MEDIA_ROUTE}/{filename}"

    def get_local_path(self, filename: str) -> Path:
        return self.ensure_directory() / filename


public_media_service = PublicMediaService()
