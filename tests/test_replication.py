import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import media_profile
import proxy
import credential_fixtures


class ReplicationTests(unittest.TestCase):
    def test_portfolio_route_is_explicit_and_loopback_only(self):
        c = config.load(ROOT / '.env.example')
        self.assertNotIn(':8010;', proxy.render(c, ROOT, https=True))
        c.update(HOMEPAGE_HOST='ohara.xdadwal.in', PORTFOLIO_PORT='8010')
        result = proxy.render(c, ROOT, https=True)
        self.assertIn('server_name xdadwal.in;', result)
        self.assertIn('server_name ohara.xdadwal.in;', result)
        self.assertIn('proxy_pass http://127.0.0.1:8010;', result)
        self.assertNotIn('@PORTFOLIO_PORT@', result)
        self.assertNotIn(':8010;', proxy.render(c, ROOT, https=False))

    def test_portfolio_rejects_admin_ports_and_bad_values(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / '.env'
            source = (ROOT / '.env.example').read_text().replace('HOMEPAGE_HOST=xdadwal.in', 'HOMEPAGE_HOST=ohara.xdadwal.in')
            for port in ['7878', '8081', '9696', '80', '-1', '65536', '8010;bad']:
                p.write_text(source.replace('PORTFOLIO_PORT=0', 'PORTFOLIO_PORT=' + port))
                with self.subTest(port=port), self.assertRaises(ValueError):
                    config.load(p)

    def test_media_profile_reruns_preserve_indexers_and_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            (root / 'configs/media').mkdir(parents=True)
            (root / 'configs/media/ohara.json').write_text((ROOT / 'configs/media/ohara.json').read_text())
            names = ['limetorrents', 'nyaasi', 'thepiratebay']
            schemas = [dict(name=n, definitionName=n, indexerUrls=['https://example.test/'],
                            fields=[{'name': 'baseUrl'}]) for n in names]
            indexers = [dict(schemas[0], id=1, enable=False)]
            naming = {name: {'renameMovies' if name == 'radarr' else 'renameEpisodes': False,
                             'format': 'operator-custom-format'} for name in ['radarr', 'sonarr']}
            calls = []
            class Client:
                def __init__(self, url, key):
                    self.name = next(n for n, p in [('radarr', '7878'), ('sonarr', '8989'), ('prowlarr', '9696')] if p in url)
                def call(self, path, body=None, method=None):
                    calls.append((self.name, path, body, method))
                    if path.endswith('/schema'): return copy.deepcopy(schemas)
                    if path.endswith('/appprofile'): return [{'id': 1}]
                    if path == '/api/v1/indexer':
                        if body is not None: indexers.append(copy.deepcopy(body))
                        return copy.deepcopy(indexers)
                    if path.endswith('/config/naming'):
                        if body is not None: naming[self.name] = copy.deepcopy(body)
                        return copy.deepcopy(naming[self.name])
                    return {}
            before = (root / '.env').read_bytes()
            with patch.object(media_profile, 'Client', Client):
                media_profile.apply(root)
                media_profile.apply(root)
            self.assertEqual(len(indexers), 3)
            self.assertFalse(indexers[0]['enable'])
            self.assertEqual((root / '.env').read_bytes(), before)
            for name, row in naming.items():
                self.assertEqual(row['format'], 'operator-custom-format')
                self.assertTrue(row['renameMovies' if name == 'radarr' else 'renameEpisodes'])
            self.assertEqual(sum(path.endswith('/indexer/test') for _, path, _, _ in calls), 2)

    def test_missing_indexer_definitions_fail_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            (root / 'configs/media').mkdir(parents=True)
            (root / 'configs/media/ohara.json').write_text(json.dumps({'rename': True, 'indexers': ['missing']}))
            with patch.object(media_profile, 'Client') as client:
                client.return_value.call.side_effect = [[], [], [{'id': 1}]]
                with self.assertRaisesRegex(ValueError, 'Unavailable'):
                    media_profile.apply(root)
                self.assertTrue(all(call.args[1:] == () for call in client.return_value.call.call_args_list))
