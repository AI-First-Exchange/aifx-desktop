from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.aifp.packager import build_aifp_package
from core.aifp.scanner import scan_project
from core.validation.validator import validate_aifx_package


class AIFPTests(unittest.TestCase):
    def test_scan_export_and_validate_working_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            root.mkdir()
            (root / "script.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "notes.md").write_text("# Notes\n", encoding="utf-8")
            (root / ".DS_Store").write_text("ignore", encoding="utf-8")

            scan = scan_project(root, version_label="v0.1")
            self.assertEqual(scan.snapshot.file_count, 2)
            self.assertIn("code", scan.snapshot.asset_counts_by_type)
            self.assertIsNone(scan.diff)

            outdir = Path(tmp) / "out"
            built = build_aifp_package(scan_result=scan, output_dir=outdir)
            self.assertTrue(built.name.endswith(".aifp-v0.1"))

            result = validate_aifx_package(built, dry_run=True)
            self.assertTrue(result["valid"], result)

    def test_rescan_diff_and_final_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo-project"
            root.mkdir()
            (root / "script.py").write_text("print('hello')\n", encoding="utf-8")

            first = scan_project(root, version_label="alpha")
            (root / "script.py").write_text("print('updated')\n", encoding="utf-8")
            (root / "image.png").write_bytes(b"\x89PNG\r\n")

            second = scan_project(
                root,
                version_label="v1.0-draft",
                mark_complete=True,
                previous_snapshot=first.to_dict(),
            )

            self.assertIsNotNone(second.diff)
            assert second.diff is not None
            self.assertEqual(second.diff.added_count, 1)
            self.assertEqual(second.diff.modified_count, 1)

            outdir = Path(tmp) / "final"
            built = build_aifp_package(scan_result=second, output_dir=outdir)
            self.assertTrue(built.name.endswith(".aifp"))

            result = validate_aifx_package(built, dry_run=True)
            self.assertTrue(result["valid"], result)


if __name__ == "__main__":
    unittest.main()
