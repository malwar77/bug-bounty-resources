import unittest
import os
import subprocess
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE_PATH = os.path.join(REPO_ROOT, "tests", "fixtures", "sample.md")
REPORT_PATH = os.path.join(REPO_ROOT, "tests", "fixtures", "report.json")


class TestCheckLinks(unittest.TestCase):
    def test_fixture_outcomes(self):
        cmd = [
            "python3",
            os.path.join(REPO_ROOT, "scripts", "check_links.py"),
            "--target-dir", FIXTURE_PATH,
            "--output-json", REPORT_PATH,
            "--quality-gate", "BROKEN_INTERNAL_FILE",
            "--warning-categories", "PASSED_EXCLUDED"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 1, f"Expected exit code 1, got {res.returncode}. Output:\n{res.stdout}")

        # Assert annotation formatting and error detection
        self.assertIn("::error file=sample.md,line=4::BROKEN_INTERNAL_FILE (HTTP 404)", res.stdout)
        self.assertIn("does_not_exist_file.md -> does_not_exist_file.md", res.stdout)
        self.assertIn("::warning file=sample.md,line=5::PASSED_EXCLUDED (HTTP 200) https://twitter.com/example", res.stdout)

        # Inspect json report
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["summary"]["failures"], 1)
        self.assertEqual(data["failures"][0]["category"], "BROKEN_INTERNAL_FILE")
        self.assertEqual(data["failures"][0]["url"], "does_not_exist_file.md")

    def test_config_validator(self):
        cmd = ["python3", os.path.join(REPO_ROOT, "scripts", "validate_config.py"), os.path.join(REPO_ROOT, "lychee.toml")]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Config validation failed: {res.stderr}")
        self.assertIn("passed all schema and value validation checks", res.stdout)


if __name__ == "__main__":
    unittest.main()
