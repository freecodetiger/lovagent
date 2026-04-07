from copy import deepcopy
import unittest
from unittest.mock import patch

from app.config import settings
from app.models.admin import RuntimeConfig
from app.models.database import SessionLocal, init_db
from app.services.runtime_config_service import RUNTIME_CONFIG_KEY, runtime_config_service


class RuntimeConfigServiceTests(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        existing = (
            self.db.query(RuntimeConfig)
            .filter(RuntimeConfig.config_key == RUNTIME_CONFIG_KEY)
            .first()
        )
        self.runtime_snapshot = deepcopy(existing.config_value) if existing else None

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

    def _clear_runtime_config(self):
        record = (
            self.db.query(RuntimeConfig)
            .filter(RuntimeConfig.config_key == RUNTIME_CONFIG_KEY)
            .first()
        )
        if record:
            self.db.delete(record)
            self.db.commit()

    def test_effective_config_prefers_runtime_values_and_falls_back_to_env(self):
        self._clear_runtime_config()

        with (
            patch.object(settings, "model_provider", "glm"),
            patch.object(settings, "zhipu_api_key", "env-key"),
            patch.object(settings, "zhipu_model", "glm-env"),
            patch.object(settings, "openai_api_key", "env-openai-key"),
            patch.object(settings, "openai_base_url", "https://env-openai.example.com/v1"),
            patch.object(settings, "openai_model", "env-openai-model"),
            patch.object(settings, "wecom_corp_id", "env-corp"),
            patch.object(settings, "wecom_agent_id", "env-agent"),
            patch.object(settings, "wecom_secret", "env-secret"),
            patch.object(settings, "wecom_token", "env-token"),
            patch.object(settings, "wecom_encoding_aes_key", "env-aes"),
            patch.object(settings, "public_base_url", "https://env.example.com"),
            patch.object(settings, "admin_password", "env-admin"),
        ):
            runtime_config_service.save_section("model", {"zhipu_model": "glm-5"})
            runtime_config_service.save_section("wecom", {"corp_id": "runtime-corp", "agent_id": "runtime-agent"})

            effective_model = runtime_config_service.get_effective_model_config()
            effective_wecom = runtime_config_service.get_effective_wecom_config()

            self.assertEqual(effective_model["zhipu_api_key"], "env-key")
            self.assertEqual(effective_model["zhipu_model"], "glm-5")
            self.assertEqual(effective_model["openai_model"], "env-openai-model")
            self.assertEqual(effective_wecom["corp_id"], "runtime-corp")
            self.assertEqual(effective_wecom["agent_id"], "runtime-agent")
            self.assertEqual(effective_wecom["secret"], "env-secret")
            self.assertEqual(runtime_config_service.get_effective_public_base_url(), "https://env.example.com")
            self.assertEqual(runtime_config_service.get_effective_admin_password(), "env-admin")

    def test_status_payload_reports_completion_and_callback_url(self):
        self._clear_runtime_config()
        runtime_config_service.save_section(
            "model",
            {
                "zhipu_api_key": "test-key",
                "zhipu_model": "glm-5",
                "zhipu_thinking_type": "disabled",
            },
        )
        runtime_config_service.save_section(
            "wecom",
            {
                "corp_id": "ww-test",
                "agent_id": "1000002",
                "secret": "secret-test",
                "token": "token-test",
                "encoding_aes_key": "encoding-test",
            },
        )
        runtime_config_service.save_section("deployment", {"public_base_url": "https://demo.trycloudflare.com"})
        runtime_config_service.save_section("admin", {"password": "secret123"})

        payload = runtime_config_service.get_status_payload()

        self.assertTrue(payload["setup_completed"])
        self.assertTrue(payload["sections"]["deployment_configured"])
        self.assertEqual(payload["current"]["model_provider"], "glm")
        self.assertEqual(payload["current"]["callback_url"], "https://demo.trycloudflare.com/wecom/callback")
        self.assertEqual(payload["raw"]["deployment"]["public_base_url"], "https://demo.trycloudflare.com")

    def test_openai_auto_model_config_uses_routed_models(self):
        self._clear_runtime_config()

        with (
            patch.object(settings, "model_provider", "glm"),
            patch.object(settings, "openai_api_key", ""),
            patch.object(settings, "openai_base_url", "https://api.openai.com/v1"),
            patch.object(settings, "openai_model", "fallback-model"),
        ):
            runtime_config_service.save_section(
                "model",
                {
                    "model_provider": "openai_compatible",
                    "openai_api_key": "openai-key",
                    "openai_base_url": "https://openrouter.example.com/v1",
                    "openai_model_mode": "auto",
                    "openai_models": {
                        "chat_model": "chat-x",
                        "memory_model": "memory-x",
                        "proactive_model": "proactive-x",
                    },
                },
            )

            effective_model = runtime_config_service.get_effective_model_config()
            self.assertEqual(effective_model["model_provider"], "openai_compatible")
            self.assertEqual(effective_model["openai_model_mode"], "auto")
            self.assertEqual(effective_model["openai_models"]["chat_model"], "chat-x")
            self.assertEqual(effective_model["openai_models"]["memory_model"], "memory-x")
            self.assertEqual(effective_model["openai_models"]["proactive_model"], "proactive-x")
            self.assertTrue(runtime_config_service.is_model_configured())

            payload = runtime_config_service.get_status_payload()
            self.assertEqual(payload["current"]["model_provider"], "openai_compatible")
            self.assertEqual(payload["current"]["openai_model_mode"], "auto")
            self.assertEqual(payload["current"]["openai_models"]["chat_model"], "chat-x")
            self.assertTrue(payload["current"]["has_openai_api_key"])


if __name__ == "__main__":
    unittest.main()
