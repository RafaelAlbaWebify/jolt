"""Regression tests for the non-destructive complexity quality gate."""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quality_complexity_gate as gate


class QualityGateTests(unittest.TestCase):
    def test_python_nested_functions_counted(self):
        source = "def outer():\n    def inner():\n        return 1\n    return inner()\n"
        self.assertEqual(dict(gate.function_lengths("x.py", source)), {"outer": 4, "inner": 2})

    def test_typescript_is_not_parsed_as_python(self):
        self.assertEqual(gate.function_lengths("x.tsx", "const x = () => 1"), [])

    def test_invalid_python_flags_syntax(self):
        self.assertEqual(gate.function_lengths("x.py", "def oops(:\n"), [("<syntax-error>", 1)])

    def test_benchmark_retains_input_size(self):
        result = gate.benchmark(3)
        self.assertEqual(result["fixture_items"], 400)
        self.assertGreater(result["encoded_bytes"], 1000)
        self.assertGreaterEqual(result["median_roundtrip_ms"], 0)

    def test_gate_uses_non_destructive_git_inventory(self):
        self.assertIsInstance(gate.tracked_sources(), list)

if __name__ == "__main__":
    unittest.main()
