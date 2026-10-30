"""Exercise actual archives in disposable repositories, never personal memory."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from bundle import package
from build_provenance import write_provenance
from verify_preview_archive import verify_preview_archive


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Preview Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.write('.gitignore', 'aura-app/dist/\naura-app/release/\nconfig/*.env\n')
        for name in ('index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', 'src/main.tsx', 'scripts/build_provenance.py'):
            self.write('aura-app/' + name, 'test source\n')
        self.commit()
        self.write('aura-app/dist/index.html', '<html>Preview</html>')
        self.write('aura-app/dist/assets/app.js', 'const preview = true;')
        write_provenance(self.root, 'web', 'aura-app/dist')

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.DEVNULL).decode().strip()

    def write(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'test source')

    def test_archive_hashes_and_commit_match_and_ignored_config_is_absent(self):
        self.write('config/keys.env', 'PRIVATE_TEST_CONFIGURATION=not-for-packaging')
        archive = package(self.root)
        verification = verify_preview_archive(self.root)
        self.assertEqual(verification["source_commit"], self.git("rev-parse", "HEAD"))
        self.assertGreater(verification["file_count"], 0)
        checksum = archive.with_suffix('.zip.sha256').read_text().split()[0]
        self.assertEqual(checksum, hashlib.sha256(archive.read_bytes()).hexdigest())
        with zipfile.ZipFile(archive) as z:
            manifest = json.loads(z.read('AURA-Companion/release-manifest.json'))
            self.assertEqual(manifest['source_commit'], self.git('rev-parse', 'HEAD'))
            self.assertEqual(manifest['scope'], 'development_preview')
            self.assertFalse(manifest['notarization_verified'])
            self.assertNotIn('AURA-Companion/config/keys.env', z.namelist())
            self.assertEqual(len(z.namelist()), len(manifest['files']) + 1)
            for name, digest in manifest['files'].items():
                self.assertNotIn('\\', name)
                self.assertEqual(digest, hashlib.sha256(z.read('AURA-Companion/' + name)).hexdigest())

    def test_archive_verifier_rejects_an_unmanifested_member(self):
        archive = package(self.root)
        with zipfile.ZipFile(archive, 'a', zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr('AURA-Companion/extra.txt', 'unexpected')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
        with self.assertRaisesRegex(ValueError, 'file list differs'):
            verify_preview_archive(self.root)

    def test_dirty_source_refused_and_old_archive_preserved(self):
        archive = package(self.root)
        original = archive.read_bytes()
        self.write('aura-app/src/main.tsx', 'changed')
        with self.assertRaisesRegex(ValueError, 'source tree must be clean'):
            package(self.root)
        self.assertEqual(archive.read_bytes(), original)

    def test_committed_source_change_requires_a_new_build(self):
        self.write('aura-app/src/main.tsx', 'new source')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Stale web build'):
            package(self.root)

    def test_changed_or_extra_generated_output_is_refused(self):
        self.write('aura-app/dist/assets/injected.js', 'unexpected')
        with self.assertRaisesRegex(ValueError, 'output changed'):
            package(self.root)

    def test_tracked_private_file_is_refused_even_if_git_allows_it(self):
        self.write('data/memory.db', 'private memory')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Private/runtime file is tracked'):
            package(self.root)

    def test_database_magic_and_known_secret_marker_are_refused(self):
        self.write('notes.txt', 'SQLite format 3' + chr(0) + 'not a real database')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Private data marker'):
            package(self.root)

    def test_additional_common_credential_families_are_refused(self):
        secrets = (
            'gho_' + 'x' * 40,
            'AKIA' + 'A' * 16,
            'AIza' + 'a' * 35,
            'npm_' + 'n' * 32,
            'xoxb-' + 's' * 30,
            'sk-' + 'k' * 48,
        )
        for index, secret in enumerate(secrets):
            with self.subTest(index=index):
                self.write('notes.txt', secret)
                self.commit()
                with self.assertRaisesRegex(ValueError, 'Private data marker'):
                    package(self.root)
        self.write('notes.txt', 'gh' + 'p_' + 'x' * 40)
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Private data marker'):
            package(self.root)

    def test_tracked_symlink_cannot_export_an_outside_file(self):
        outside = self.root.parent / (self.root.name + '-outside.txt')
        outside.write_text('private outside content')
        try:
            (self.root / 'leak.txt').symlink_to(outside)
            self.commit()
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                package(self.root)
        finally:
            outside.unlink()

    def test_generated_symlink_is_refused(self):
        (self.root / 'aura-app/dist/assets/link').symlink_to(self.root / 'aura-app/src', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            package(self.root)

    def test_output_symlink_cannot_overwrite_an_outside_file(self):
        out = self.root / 'aura-app/release'
        out.mkdir()
        target = self.root / 'aura-app/dist/index.html'
        original = target.read_text()
        (out / 'AURA-Companion-0.3.0-preview.zip').symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            package(self.root)
        self.assertEqual(target.read_text(), original)


if __name__ == '__main__':
    unittest.main()
