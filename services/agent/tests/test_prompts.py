import unittest

from opspilot_agent.prompts import REMEDIATION_INSTRUCTIONS, SYSTEM_INSTRUCTIONS, build_investigation_prompt


class PromptTests(unittest.TestCase):
    def test_instructions_enforce_read_only_evidence(self):
        self.assertIn("read-only", SYSTEM_INSTRUCTIONS)
        self.assertIn("k8s_get_pod_logs", SYSTEM_INSTRUCTIONS)
        self.assertIn("HIGH model", SYSTEM_INSTRUCTIONS)
        self.assertIn("search_knowledge", SYSTEM_INSTRUCTIONS)
        self.assertIn("source of truth", SYSTEM_INSTRUCTIONS)
        self.assertIn("github_compare_commits", SYSTEM_INSTRUCTIONS)
        self.assertIn("deployed revision", SYSTEM_INSTRUCTIONS)

    def test_prompt_contains_namespace_and_query(self):
        prompt = build_investigation_prompt("why is payment failing?", "opspilot-demo", github_enabled=True)
        self.assertIn("opspilot-demo", prompt)
        self.assertIn("why is payment failing?", prompt)
        self.assertIn("knowledge base", prompt)
        self.assertIn("GitHub change intelligence is enabled", prompt)


    def test_remediation_instructions_require_human_approval(self):
        self.assertIn("Human-approved remediation is enabled", REMEDIATION_INSTRUCTIONS)
        self.assertIn("external human approval", REMEDIATION_INSTRUCTIONS)
        self.assertIn("Never assume approval was granted", REMEDIATION_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
