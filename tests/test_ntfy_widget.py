"""Reader security boundaries and Homepage credential isolation."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lib'))
import config
import credentials
import ntfy


class ReaderTests(unittest.TestCase):
    def test_reader_preserves_publisher_and_is_read_only_idempotently(self):
        before={'auth-default-access':'deny-all','enable-signup':False,
                'auth-users':['admin:existing-hash:user'],'auth-access':['admin:ohara-alerts:rw']}
        after=ntfy.reader_config(before,'Test-only-independent-reader')
        self.assertEqual(before['auth-users'],['admin:existing-hash:user'])
        self.assertEqual(after['auth-users'][0],before['auth-users'][0])
        self.assertEqual(after['auth-access'],['admin:ohara-alerts:rw','homepage-reader:ohara-alerts:ro'])
        self.assertEqual(ntfy.reader_config(after,'Test-only-independent-reader'),after)
        with self.assertRaises(ValueError):ntfy.reader_config(after,'Changed-password-not-implicit')
        after['auth-access'][-1]='homepage-reader:*:rw'
        with self.assertRaises(ValueError):ntfy.reader_config(after,'Test-only-independent-reader')

    def test_read_publish_and_unrelated_topic_permissions_verified(self):
        with patch.object(ntfy,'request',side_effect=[(200,b''),(403,b''),(403,b'')]):
            ntfy.verify_reader('test-only-reader-password')
        for codes in ([200,200],[200,403,200],[401]):
            with patch.object(ntfy,'request',side_effect=[(c,b'') for c in codes]),self.assertRaises(ValueError):
                ntfy.verify_reader('test-only-reader-password')

    def test_only_dedicated_reader_alias_reaches_homepage(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'.env'
            p.write_text('NTFY_PASSWORD=Test-publisher-private\nNTFY_HOMEPAGE_PASSWORD=Test-reader-independent\n');p.chmod(0o600)
            media={k:'fixture-only' for k in ['RADARR_API_KEY','SONARR_API_KEY','LIDARR_API_KEY','QBITTORRENT_PASSWORD']}
            env=credentials.admin_widget_environment(root,media)
            self.assertEqual(env['HOMEPAGE_VAR_NTFY_PASSWORD'],'Test-reader-independent')
            self.assertNotIn('NTFY_PASSWORD',env)
            self.assertNotIn('Test-publisher-private',env.values())
            p.write_text('NTFY_PASSWORD=Test-publisher-private\n')
            self.assertNotIn('HOMEPAGE_VAR_NTFY_PASSWORD',credentials.admin_widget_environment(root,media))

    def test_widget_has_only_placeholder_for_reader_password(self):
        c=config.load(Path(__file__).resolve().parents[1]/'.env.example')
        p=ntfy.widget_profile(c)
        self.assertEqual(p['username'],'homepage-reader')
        self.assertEqual(p['password'],'{{HOMEPAGE_VAR_NTFY_PASSWORD}}')
        self.assertEqual(p['type'],'ntfy')
