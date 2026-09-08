import unittest

from opspilot_agent.prompts import SYSTEM_INSTRUCTIONS, build_investigation_prompt


class PromptTests(unittest.TestCase):
    def test_instructions_enforce_read_only_evidence(self):
        self.assertIn("read-only", SYSTEM_INSTRUCTIONS)
        self.assertIn("k8s_get_pod_logs", SYSTEM_INSTRUCTIONS)
        self.assertIn("HIGH confidence", SYSTEM_INSTRUCTIONS)
        self.assertIn("search_knowledge", SYSTEM_INSTRUCTIONS)
        self.assertIn("source of truth", SYSTEM_INSTRUCTIONS)

    def test_prompt_contains_namespace_and_query(self):
        prompt = build_investigation_prompt("why is payment failing?", "opspilot-demo")
        self.assertIn("opspilot-demo", prompt)
        self.assertIn("why is payment failing?", prompt)
        self.assertIn("knowledge base", prompt)


if __name__ == "__main__":
    unittest.main()
