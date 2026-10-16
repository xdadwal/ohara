import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
import runtime

class StatusTests(unittest.TestCase):
    def test_homepage_check_respects_configured_host_validation(self):
        services = ['homepage', 'seerr', 'speedtest',
                    'jellyfin', 'navidrome', 'radarr', 'sonarr', 'lidarr', 'bazarr', 'prowlarr', 'qbittorrent']
        rows = [{'Service': s, 'State': 'running', 'Health': 'healthy'} for s in services]
        def endpoint(request, timeout):
            if ':3002/' in request.full_url and request.get_header('Host') != 'ohara.example.test':
                raise urllib.error.HTTPError(request.full_url, 400, 'Host validation failed', {}, None)
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.status = 200
            return response
        with patch.object(runtime, 'compose', return_value=json.dumps(rows)), \
             patch.object(runtime.urllib.request, 'urlopen', side_effect=endpoint), \
             patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(runtime.status({'DOMAIN': 'example.test', 'HOMEPAGE_HOST': 'ohara.example.test'}, Path('/unused')), 0)

    def test_lidarr_and_bazarr_protected_endpoints_are_reachable(self):
        services = ['homepage', 'seerr', 'speedtest', 'jellyfin', 'navidrome', 'radarr',
                    'sonarr', 'lidarr', 'bazarr', 'prowlarr', 'qbittorrent']
        rows = [{'Service': s, 'State': 'running'} for s in services]
        visited = []
        def endpoint(request, timeout):
            visited.append(request.full_url)
            if ':8686/' in request.full_url or ':6767/' in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 401, 'Authentication required', {}, None)
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.status = 200
            return response
        with patch.object(runtime, 'compose', return_value=json.dumps(rows)), \
             patch.object(runtime.urllib.request, 'urlopen', side_effect=endpoint), \
             patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(runtime.status({'HOMEPAGE_HOST': 'ohara.example.test'}, Path('/unused')), 0)
        self.assertIn('http://127.0.0.1:8686/ping', visited)
        self.assertIn('http://127.0.0.1:4533/ping', visited)
        self.assertIn('http://127.0.0.1:6767/', visited)

    def test_lidarr_or_bazarr_missing_or_unreachable_fails(self):
        services = ['homepage', 'seerr', 'speedtest', 'jellyfin', 'navidrome', 'radarr',
                    'sonarr', 'lidarr', 'bazarr', 'prowlarr', 'qbittorrent']
        for missing in ['lidarr', 'bazarr', 'navidrome']:
            rows = [{'Service': s, 'State': 'running'} for s in services if s != missing]
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.status = 200
            with self.subTest(missing=missing), \
                 patch.object(runtime, 'compose', return_value=json.dumps(rows)), \
                 patch.object(runtime.urllib.request, 'urlopen', return_value=response), \
                 patch('sys.stdout', new=io.StringIO()):
                self.assertEqual(runtime.status({'HOMEPAGE_HOST': 'ohara.example.test'}, Path('/unused')), 1)
