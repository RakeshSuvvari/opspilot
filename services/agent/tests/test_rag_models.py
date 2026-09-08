import unittest

from opspilot_agent.rag.models import KnowledgeHit


class RagModelTests(unittest.TestCase):
    def test_hit_serialization_rounds_similarity(self):
        hit = KnowledgeHit(
            title="Runbook",
            source_path="knowledge/runbooks/example.md",
            document_type="runbook",
            service=None,
            chunk_index=0,
            heading="Diagnosis",
            content="Inspect logs.",
            similarity=0.876543,
        )
        payload = hit.as_dict()
        self.assertEqual(payload["similarity"], 0.8765)
        self.assertEqual(payload["document_type"], "runbook")


if __name__ == "__main__":
    unittest.main()
