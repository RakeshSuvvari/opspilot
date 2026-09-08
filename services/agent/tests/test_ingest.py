import ast
import unittest
from pathlib import Path


class IngestImplementationTests(unittest.TestCase):
    def test_bulk_insert_uses_cursor_executemany(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "opspilot_agent"
            / "rag"
            / "ingest.py"
        )
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        calls = [
            node.func
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        executemany_receivers = [
            func.value.id
            for func in calls
            if func.attr == "executemany" and isinstance(func.value, ast.Name)
        ]

        self.assertIn("cur", executemany_receivers)
        self.assertNotIn("conn", executemany_receivers)
        self.assertIn("with conn.cursor() as cur:", source)


if __name__ == "__main__":
    unittest.main()
