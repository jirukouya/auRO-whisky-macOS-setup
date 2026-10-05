from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'verify.yml'

class CIWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding='utf-8')

    def test_workflow_is_present_and_runs_on_main_changes(self) -> None:
        self.assertTrue(WORKFLOW.is_file())
        self.assertIn('pull_request:', self.source)
        self.assertIn('push:', self.source)
        self.assertIn('branches: [main]', self.source)

    def test_workflow_uses_read_only_deterministic_runner(self) -> None:
        self.assertIn('permissions:', self.source)
        self.assertIn('  contents: read', self.source)
        self.assertIn('runs-on: macos-15', self.source)
        self.assertIn("python-version: '3.12'", self.source)
        self.assertIn('actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683', self.source)
        self.assertIn('fetch-depth: 0', self.source)
        self.assertIn('actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065', self.source)
        self.assertNotIn('contents: write', self.source)
        self.assertNotIn('secrets.', self.source)
        self.assertNotIn('sudo ', self.source)

    def test_workflow_covers_repository_native_checks_without_live_claims(self) -> None:
        for command in (
            'python3 -m py_compile scripts/*.py tests/*.py',
            "python3 -B -m unittest discover -s tests -p 'test_*.py'",
            'python3 -B tests/phase2a.py --run',
            'git diff --check \"origin/$GITHUB_BASE_REF...HEAD\"',
            'git diff --check \"$GITHUB_EVENT_BEFORE..$GITHUB_SHA\"',
        ):
            self.assertIn(command, self.source)
        self.assertNotIn('run: python3 -B tests/test_whisky.py', self.source)
        self.assertNotIn('run: python3 -B tests/test_azzyai.py', self.source)
        for live_or_privileged in (
            'run: wine',
            'run: whisky',
            'run: osascript',
            'run: security',
            'run: open ',
            'brew install',
        ):
            self.assertNotIn(live_or_privileged, self.source.lower())

if __name__ == '__main__':
    unittest.main()
