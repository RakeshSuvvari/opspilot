import os
import unittest
from unittest.mock import patch

from opspilot_agent.config import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.openai_model, "gpt-5.6-terra")
        self.assertEqual(settings.k8s_mcp_url, "http://localhost:8080/mcp")
        self.assertEqual(settings.default_namespace, "opspilot-demo")
        self.assertEqual(settings.max_turns, 12)
        self.assertFalse(settings.trace_sensitive_data)
        self.assertTrue(settings.rag_enabled)
        self.assertEqual(settings.embedding_model, "text-embedding-3-small")
        self.assertEqual(settings.embedding_dimensions, 1536)
        self.assertEqual(settings.database_name, "opspilot")

    def test_invalid_mcp_url(self):
        with patch.dict(
            os.environ,
            {"OPSPILOT_K8S_MCP_URL": "localhost:8080/mcp"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_invalid_embedding_dimensions(self):
        with patch.dict(
            os.environ,
            {"OPSPILOT_EMBEDDING_DIMENSIONS": "1024"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_openai_key_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        with self.assertRaises(ValueError):
            settings.require_openai_key()


if __name__ == "__main__":
    unittest.main()
