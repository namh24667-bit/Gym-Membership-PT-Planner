from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from test_local06a import load_release


class UpgradeCompatibilityTests(TestCase):
    def test_only_exact_original_version_can_add_the_sql_step(self):
        release = load_release()
        old = dict(release='0.9.0-test', sql_steps=release.BASE_STEPS)
        new = dict(release='0.9.1-test', sql_steps=release.BASE_STEPS + [release.UPGRADE_STEP])
        self.assertTrue(release.needs_sql_upgrade(old, new))
        self.assertFalse(release.needs_sql_upgrade(new, new))
        for source in ('0.8.0-test', '0.9.0-test.1', '0.9.1-test'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                release.needs_sql_upgrade(dict(old, release=source), new)

    def test_wrong_archive_hash_is_rejected_before_archive_or_installation_access(self):
        release = load_release()
        with TemporaryDirectory() as scratch, patch.object(release, 'read_archive') as open_archive:
            artifact = Path(scratch) / 'package.zip'
            artifact.write_bytes(b'synthetic test archive')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                release.update(artifact, None, '0' * 64)
            open_archive.assert_not_called()
