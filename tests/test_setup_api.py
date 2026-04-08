import contextlib
from copy import deepcopy
import unittest
from unittest.mock import AsyncMock, patch

from app.config import settings
from fastapi.testclient import TestClient

from app.main import app
from app.models.admin import RuntimeConfig
from app.models.database import SessionLocal, init_db
from app.services.runtime_config_service import RUNTIME_CONFIG_KEY
from app.services.setup_service import setup_service


class SetupApiTests(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        existing = (
            self.db.query(RuntimeConfig)
            .filter(RuntimeConfig.config_key == RUNTIME_CONFIG_KEY)
            .first()
        )
        self.runtime_snapshot = deepcopy(existing.config_value) if existing else None
        if existing:
            self.db.delete(existing)
            self.db.commit()

        self.settings_patches = contextlib.ExitStack()
        self.settings_patches.enter_context(patch.object(settings, "model_provider", "glm"))
        self.settings_patches.enter_context(patch.object(settings, "zhipu_api_key", ""))
        self.settings_patches.enter_context(patch.object(settings, "zhipu_multimodal_api_key", ""))
        self.settings_patches.enter_context(patch.object(settings, "zhipu_multimodal_model", "glm-4.6v"))
        self.settings_patches.enter_context(patch.object(settings, "openai_api_key", ""))
        self.settings_patches.enter_context(patch.object(settings, "openai_base_url", "https://api.openai.com/v1"))
        self.settings_patches.enter_context(patch.object(settings, "openai_model", "gpt-4o-mini"))
        self.settings_patches.enter_context(patch.object(settings, "wecom_corp_id", ""))
        self.settings_patches.enter_context(patch.object(settings, "wecom_agent_id", ""))
        self.settings_patches.enter_context(patch.object(settings, "wecom_secret", ""))
        self.settings_patches.enter_context(patch.object(settings, "wecom_token", ""))
        self.settings_patches.enter_context(patch.object(settings, "wecom_encoding_aes_key", ""))
        self.settings_patches.enter_context(patch.object(settings, "public_base_url", ""))
        self.settings_patches.enter_context(patch.object(settings, "admin_password", ""))
        self.settings_patches.enter_context(patch.object(settings, "server_host", "127.0.0.1"))
        self.lifespan_tunnel_patcher = patch("app.main.tunnel_service.ensure_started", return_value=None)
        self.lifespan_tunnel_patcher.start()
        self.client = TestClient(app)

    def tearDown(self):
        record = (
            self.db.query(RuntimeConfig)
            .filter(RuntimeConfig.config_key == RUNTIME_CONFIG_KEY)
            .first()
        )
        if self.runtime_snapshot is None:
            if record:
                self.db.delete(record)
        else:
            if not record:
                record = RuntimeConfig(config_key=RUNTIME_CONFIG_KEY)
                self.db.add(record)
            record.config_value = deepcopy(self.runtime_snapshot)

        self.db.commit()
        self.db.close()
        self.settings_patches.close()
        self.lifespan_tunnel_patcher.stop()
        self.client.close()

    def _setup_status_patches(self):
        return (
            patch("app.services.setup_service.tunnel_service.ensure_started", return_value=None),
            patch(
                "app.services.setup_service.tunnel_service.get_status",
                return_value={
                    "available": False,
                    "running": False,
                    "public_url": "",
                    "binary_path": "",
                },
            ),
        )

    def test_setup_status_returns_expected_structure(self):
        ensure_patch, status_patch = self._setup_status_patches()
        with ensure_patch, status_patch:
            response = self.client.get("/setup/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("setup_completed", payload)
        self.assertIn("sections", payload)
        self.assertIn("current", payload)
        self.assertIn("raw", payload)
        self.assertIn("tunnel", payload)
        self.assertFalse(payload["setup_completed"])

    def test_setup_config_endpoints_persist_sections(self):
        ensure_patch, status_patch = self._setup_status_patches()
        with ensure_patch, status_patch:
            model_response = self.client.put(
                "/setup/config/model",
                json={
                    "zhipu_api_key": "test-key",
                    "zhipu_model": "glm-5",
                    "zhipu_thinking_type": "disabled",
                },
            )
            wecom_response = self.client.put(
                "/setup/config/wecom",
                json={
                    "corp_id": "ww-test",
                    "agent_id": "1000002",
                    "secret": "secret-test",
                    "token": "token-test",
                    "encoding_aes_key": "encoding-test",
                    "public_base_url": "https://demo.trycloudflare.com",
                },
            )
            admin_response = self.client.put(
                "/setup/config/admin",
                json={"password": "secret123"},
            )

        self.assertEqual(model_response.status_code, 200)
        self.assertTrue(model_response.json()["sections"]["model_configured"])

        self.assertEqual(wecom_response.status_code, 200)
        self.assertEqual(wecom_response.json()["current"]["callback_url"], "https://demo.trycloudflare.com/wecom/callback")

        self.assertEqual(admin_response.status_code, 200)
        self.assertTrue(admin_response.json()["sections"]["admin_configured"])
        self.assertTrue(admin_response.json()["setup_completed"])

    def test_setup_model_endpoint_supports_openai_compatible_auto_mode(self):
        ensure_patch, status_patch = self._setup_status_patches()
        with ensure_patch, status_patch:
            response = self.client.put(
                "/setup/config/model",
                json={
                    "model_provider": "openai_compatible",
                    "openai_api_key": "openai-key",
                    "openai_base_url": "https://openrouter.example.com/v1",
                    "multimodal_api_key": "mm-key",
                    "multimodal_model": "glm-4.6v",
                    "openai_model_mode": "auto",
                    "openai_model": "",
                    "openai_models": {
                        "chat_model": "chat-x",
                        "memory_model": "memory-x",
                        "proactive_model": "proactive-x",
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["sections"]["model_configured"])
        self.assertEqual(payload["current"]["model_provider"], "openai_compatible")
        self.assertEqual(payload["current"]["openai_model_mode"], "auto")
        self.assertEqual(payload["current"]["openai_base_url"], "https://openrouter.example.com/v1")
        self.assertEqual(payload["current"]["openai_models"]["memory_model"], "memory-x")
        self.assertEqual(payload["current"]["multimodal_model"], "glm-4.6v")
        self.assertTrue(payload["current"]["multimodal_configured"])
        self.assertTrue(payload["current"]["has_multimodal_api_key"])
        self.assertTrue(payload["current"]["has_openai_api_key"])

    def test_setup_model_endpoint_rejects_incomplete_openai_manual_config(self):
        ensure_patch, status_patch = self._setup_status_patches()
        with ensure_patch, status_patch:
            response = self.client.put(
                "/setup/config/model",
                json={
                    "model_provider": "openai_compatible",
                    "openai_api_key": "openai-key",
                    "openai_base_url": "https://openrouter.example.com/v1",
                    "openai_model_mode": "manual",
                    "openai_model": "",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "手动模式下必须填写模型名称")

    def test_validate_endpoint_returns_structured_checks(self):
        ensure_patch, status_patch = self._setup_status_patches()
        with ensure_patch, status_patch:
            self.client.put(
                "/setup/config/model",
                json={
                    "zhipu_api_key": "test-key",
                    "zhipu_model": "glm-5",
                    "zhipu_thinking_type": "disabled",
                },
            )
            self.client.put(
                "/setup/config/wecom",
                json={
                    "corp_id": "ww-test",
                    "agent_id": "1000002",
                    "secret": "secret-test",
                    "token": "token-test",
                    "encoding_aes_key": "encoding-test",
                    "public_base_url": "https://demo.trycloudflare.com",
                },
            )
            self.client.put("/setup/config/admin", json={"password": "secret123"})
            self.client.post("/admin-api/auth/login", json={"password": "secret123"})

            with (
                patch.object(setup_service, "_check_local_health", AsyncMock(return_value={"ok": True, "detail": "http://127.0.0.1:8000/health"})),
                patch.object(setup_service, "_check_public_health", AsyncMock(return_value={"ok": True, "detail": "https://demo.trycloudflare.com/health"})),
                patch.object(setup_service, "_check_model", AsyncMock(return_value={"ok": True, "detail": "ok"})),
                patch.object(setup_service, "_check_wecom", return_value={"ok": True, "detail": "token ok"}),
            ):
                response = self.client.post("/setup/validate")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["all_passed"])
        self.assertEqual(set(payload["checks"].keys()), {"local_health", "public_health", "model", "wecom", "callback"})
        self.assertTrue(payload["status"]["setup_completed"])


if __name__ == "__main__":
    unittest.main()
