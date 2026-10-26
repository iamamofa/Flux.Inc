"""Exercise the proposal guard against real temporary Git repositories."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from dashboard_changes import ProposalError, apply_patch, export_patch, git, validate_path


class DashboardProposalTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'source'
        self.root.mkdir()
        git(self.root, 'init', '-q')
        git(self.root, 'config', 'user.name', 'Workflow test')
        git(self.root, 'config', 'user.email', 'workflow@example.invalid')
        self.write('inventory/views.py', 'original = True\n')
        self.write('inventory/templates/inventory/home.html', 'Original carousel\n')
        self.write('requirements-runtime.txt', 'Django==4.1.7\n')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-qm', 'Initial fixture')
        self.base = git(self.root, 'rev-parse', 'HEAD').decode().strip()
        self.patch = Path(self.directory.name) / 'proposal.patch'

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def test_exports_and_applies_a_new_dashboard_feature(self):
        self.write('inventory/views.py', 'dashboard_feature = True\n')
        self.write('static/js/dashboard_accessibility.js', 'const accessible = true;\n')
        self.assertTrue(export_patch(self.root, self.base, self.patch))
        target = Path(self.directory.name) / 'verification'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(target)], check=True)
        apply_patch(target, 'HEAD', self.patch)
        self.assertEqual((target / 'inventory/views.py').read_text(), 'dashboard_feature = True\n')
        self.assertTrue((target / 'static/js/dashboard_accessibility.js').exists())
        self.assertEqual((target / 'inventory/templates/inventory/home.html').read_text(), 'Original carousel\n')

    def test_protects_the_original_home_screen(self):
        self.write('inventory/templates/inventory/home.html', 'Changed home\n')
        with self.assertRaises(ProposalError):
            export_patch(self.root, self.base, self.patch)

    def test_rejects_protected_files(self):
        for name in (
            'requirements-runtime.txt', '.github/workflows/other.yml', 'db.sqlite3',
            'inventory/models.py', 'inventory/migrations/9999_change.py', '.env',
        ):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes() if path.exists() else None
                try:
                    self.write(name, 'unexpected change\n')
                    with self.assertRaises(ProposalError):
                        export_patch(self.root, self.base, self.patch)
                finally:
                    if original is None:
                        path.unlink()
                    else:
                        path.write_bytes(original)

    def test_rejects_deleting_dashboard_code(self):
        (self.root / 'inventory/views.py').unlink()
        with self.assertRaises(ProposalError):
            export_patch(self.root, self.base, self.patch)

    def test_rejects_source_symlinks(self):
        path = self.root / 'inventory/dashboard_link.py'
        path.symlink_to(self.root / 'requirements-runtime.txt')
        with self.assertRaises(ProposalError):
            export_patch(self.root, self.base, self.patch)

    def test_includes_changes_even_if_agent_created_a_commit(self):
        self.write('inventory/views.py', 'dashboard_feature = True\n')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-qm', 'Unexpected agent commit')
        self.assertTrue(export_patch(self.root, self.base, self.patch))
        self.assertIn(b'dashboard_feature', self.patch.read_bytes())

    def test_rejects_patches_touching_protected_paths(self):
        self.write('inventory/templates/inventory/home.html', 'Changed home\n')
        self.patch.write_bytes(git(self.root, 'diff', self.base))
        target = Path(self.directory.name) / 'verification'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(target)], check=True)
        with self.assertRaises(ProposalError):
            apply_patch(target, 'HEAD', self.patch)
        self.assertEqual((target / 'inventory/templates/inventory/home.html').read_text(), 'Original carousel\n')

    def test_clean_checkout_produces_no_proposal(self):
        self.assertFalse(export_patch(self.root, self.base, self.patch))
        self.assertFalse(self.patch.exists())

    def test_reverted_staged_home_edit_is_not_exported(self):
        self.write('inventory/templates/inventory/home.html', 'Changed home\n')
        git(self.root, 'add', '.')
        self.write('inventory/templates/inventory/home.html', 'Original carousel\n')
        self.write('inventory/views.py', 'dashboard_feature = True\n')
        self.assertTrue(export_patch(self.root, self.base, self.patch))
        self.assertNotIn(b'home.html', self.patch.read_bytes())

    def test_rejects_binary_content_in_source_files(self):
        (self.root / 'inventory/views.py').write_bytes(b'\xff\xfe')
        with self.assertRaises(ProposalError):
            export_patch(self.root, self.base, self.patch)

    def test_patterns_cannot_match_unrelated_directory_trees(self):
        for path in ('outside/inventory/dashboard_test.py', '../inventory/views.py', '/inventory/views.py'):
            with self.subTest(path=path), self.assertRaises(ProposalError):
                validate_path(path)


if __name__ == '__main__':
    unittest.main()
