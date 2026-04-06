"""
Cloudflare Tunnel 管理服务
"""

import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Dict, Optional

from app.config import settings
from app.services.runtime_config_service import runtime_config_service


PUBLIC_URL_PATTERN = re.compile(r"https://[A-Za-z0-9._-]+(?:trycloudflare\.com|[A-Za-z0-9.-]+)")


class TunnelService:
    """管理本地 cloudflared quick tunnel。"""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._public_url: str = ""
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None

    def _find_binary(self) -> Optional[str]:
        candidates = [
            shutil.which("cloudflared"),
            str(Path(__file__).resolve().parent.parent.parent / ".tools" / "bin" / "cloudflared"),
            "/usr/local/bin/cloudflared",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    def is_available(self) -> bool:
        return bool(self._find_binary())

    def get_status(self) -> Dict:
        process_running = self._process is not None and self._process.poll() is None
        public_url = self._public_url or runtime_config_service.get_effective_public_base_url()
        return {
            "available": self.is_available(),
            "running": process_running,
            "public_url": public_url,
            "binary_path": self._find_binary() or "",
        }

    def ensure_started(self) -> Dict:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.get_status()

            binary = self._find_binary()
            if not binary:
                return self.get_status()

            command = [
                binary,
                "tunnel",
                "--url",
                f"http://127.0.0.1:{settings.server_port}",
                "--no-autoupdate",
            ]
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._reader_thread = threading.Thread(target=self._consume_output, daemon=True)
            self._reader_thread.start()
            return self.get_status()

    def restart(self) -> Dict:
        self.stop()
        return self.ensure_started()

    def stop(self) -> None:
        with self._lock:
            if self._process is None:
                return
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None

    def _consume_output(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return

        for line in process.stdout:
            match = PUBLIC_URL_PATTERN.search(line)
            if not match:
                continue

            public_url = match.group(0).rstrip("/")
            self._public_url = public_url
            runtime_config_service.save_section("deployment", {"public_base_url": public_url})


tunnel_service = TunnelService()
