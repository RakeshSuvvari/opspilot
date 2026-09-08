import unittest

from opspilot_agent.rag.chunking import chunk_markdown, extract_title, parse_front_matter


class ChunkingTests(unittest.TestCase):
    def test_front_matter(self):
        metadata, body = parse_front_matter(
            "---\nservice: payment\ndocument_type: runbook\n---\n# Title\nBody"
        )
        self.assertEqual(metadata["service"], "payment")
        self.assertTrue(body.startswith("# Title"))

    def test_extract_title(self):
        text = "# Payment Runbook\n\nSome content"
        self.assertEqual(extract_title(text, "fallback"), "Payment Runbook")

    def test_heading_is_preserved(self):
        chunks = chunk_markdown("# Runbook\n\n## Diagnosis\nCheck logs and events.")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading, "Diagnosis")
        self.assertIn("Check logs", chunks[0].content)

    def test_large_section_is_split(self):
        text = "## Details\n" + ("failure evidence sentence. " * 80)
        chunks = chunk_markdown(text, max_chars=400, overlap_chars=50)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.heading == "Details" for chunk in chunks))

    def test_invalid_overlap(self):
        with self.assertRaises(ValueError):
            chunk_markdown("content", max_chars=300, overlap_chars=300)


if __name__ == "__main__":
    unittest.main()
