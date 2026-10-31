import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ige"


class NoQwenFallbackTests(unittest.TestCase):
    def test_cli_does_not_fallback_from_grok_to_qwen(self):
        text = (SRC / "cli.py").read_text(encoding="utf-8")
        # Grok and Qwen are explicit branches; no except-import-qwen pattern.
        self.assertIn('args.reasoner == "grok"', text)
        self.assertIn('args.reasoner == "qwen"', text)
        self.assertNotIn("except", text.split("if args.reasoner == \"grok\"")[1].split("elif args.reasoner == \"qwen\"")[0])

    def test_xai_grok_module_does_not_import_qwen_or_transformers(self):
        tree = ast.parse((SRC / "read" / "providers" / "xai_grok.py").read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        joined = " ".join(imported)
        self.assertNotIn("transformers", joined)
        self.assertNotIn("qwen", joined.lower())

    def test_qwen_module_is_marked_deprecated(self):
        text = (SRC / "read" / "providers" / "qwen3_vl.py").read_text(encoding="utf-8")
        self.assertIn("DEPRECATED", text)
        self.assertIn("DeprecationWarning", text)
