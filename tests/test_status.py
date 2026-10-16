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
        services = ['homepage', 'seerr', 'copyparty', 'speedtest', 'pihole',
                    'jellyfin', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent']
        rows = [{'Service': s, 'State': 'running', 'Health': 'healthy'} for s in services]
        def endpoint(request, timeout):
            if ':3002/' in request.full_url and request.get_header('Host') != 'example.test':
                raise urllib.error.HTTPError(request.full_url, 400, 'Host validation failed', {}, None)
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.status = 200
            return response
        with patch.object(runtime, 'compose', return_value=json.dumps(rows)), \
             patch.object(runtime.urllib.request, 'urlopen', side_effect=endpoint), \
             patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(runtime.status({'DOMAIN': 'example.test'}, Path('/unused')), 0)
