from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from zipfile import ZipFile

from app import create_app
from app.portable_config import identifier, validate_scope


def load_release():
    script = Path(__file__).resolve().parents[1] / 'ops/portable/release.py'
    spec = spec_from_file_location('team_release', script)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortableTargetTests(TestCase):
    def test_only_local_named_or_default_windows_sql_instance(self):
        values = ('IronPulse_InstallQA', r'TEAM-PC\IronPulseTeamApp', 'TEAM-PC')
        self.assertEqual(validate_scope(r'lpc:TEAM-PC\EXPRESS2', *values), ('TEAM-PC', 'EXPRESS2'))
        self.assertEqual(validate_scope('lpc:TEAM-PC', *values), ('TEAM-PC', ''))
        for server in (r'lpc:OTHER\EXPRESS2', r'tcp:TEAM-PC\EXPRESS2', 'lpc:TEAM-PC;UID=test'):
            with self.subTest(server=server), self.assertRaises(ValueError):
                validate_scope(server, *values)

    def test_protected_databases_and_missing_identity_are_refused(self):
        for name in ('master', 'model', 'IronPulse', 'ironpulse_perfQA', 'IronPulse_Demo'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_scope('lpc:TEAM-PC', name, r'TEAM-PC\TeamApp', 'TEAM-PC')
        with self.assertRaises(ValueError):
            identifier('00000000-0000-0000-0000-000000000000')

    def test_each_installation_has_its_own_loopback_cookie(self):
        config = dict(LOCAL_QA=True, LOCAL_HTTP=True, PORTABLE_QA=True,
                      SQL_SERVER=r'lpc:TEAM-PC\EXPRESS2', SQL_DATABASE='IronPulse_InstallQA',
                      SQL_WINDOWS_LOGIN=r'TEAM-PC\TeamApp', PORTABLE_INSTALL_ID='22345678-1234-1234-1234-123456789abc',
                      SQL_QA_BROKER_GUID='12345678-1234-1234-1234-123456789abc')
        with patch.dict('os.environ', {'COMPUTERNAME': 'TEAM-PC'}):
            app = create_app(config)
            another = create_app(dict(config, PORTABLE_INSTALL_ID='32345678-1234-1234-1234-123456789abc'))
        self.assertNotEqual(app.config['SESSION_COOKIE_NAME'], another.config['SESSION_COOKIE_NAME'])
        self.assertFalse(app.config['SESSION_COOKIE_SECURE'])
        self.assertEqual(app.test_client().get('/login', headers={'X-Forwarded-Host': 'outside'}).status_code, 403)


class ReleaseTests(TestCase):
    def test_allowlist_excludes_secrets_and_windows_special_paths(self):
        release = load_release()
        self.assertTrue(release.allowed('app/templates/local04/member.html'))
        for name in ('instance/portable.json', '.venv/Scripts/python.exe', 'app/NUL.py',
                     '../app/db.py', 'app/./db.py', r'app\portable_config.py', 'ops/sql-02/verify.py',
                     'app/templates/private-key.pem'):
            with self.subTest(name=name):
                self.assertFalse(release.allowed(name))

    def test_unlisted_zip_entry_refused_before_any_extraction(self):
        release = load_release()
        with TemporaryDirectory() as work:
            path = Path(work) / 'hostile.zip'
            with ZipFile(path, 'w') as archive:
                archive.writestr('app/../instance/portable.json', '{}')
            with self.assertRaises(ValueError):
                release.read_archive(path)
            self.assertEqual(list(Path(work).iterdir()), [path])

    def test_update_orders_versions_and_rejects_unpinned_input(self):
        release = load_release()
        self.assertLess(release.version_tuple('0.9.0-test'), release.version_tuple('0.9.0-test.1'))
        self.assertLess(release.version_tuple('0.9.0-test.1'), release.version_tuple('0.9.1-test'))
        with self.assertRaises(ValueError):
            release.version_tuple('latest')
