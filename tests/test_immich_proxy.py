import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('immich_proxy', str(ROOT / 'scripts/immich-proxy'))
spec = importlib.util.spec_from_loader(loader.name, loader)
proxy = importlib.util.module_from_spec(spec)
loader.exec_module(proxy)


class ImmichProxyTests(unittest.TestCase):
    def test_render_has_dedicated_host_uploads_websockets_and_edge_headers(self):
        text = proxy.render()
        self.assertNotIn('${', text)
        self.assertEqual(text.count('server_name immich.xdadwal.in;'), 2)
        for required in ('127.0.0.1:2283', 'client_max_body_size 50000M;',
                         'proxy_request_buffering off;', 'proxy_read_timeout 600s;',
                         'proxy_set_header Upgrade $http_upgrade;',
                         'proxy_set_header X-Forwarded-For $remote_addr;',
                         'ssl_protocols TLSv1.2 TLSv1.3;', '/.well-known/acme-challenge/'):
            self.assertIn(required, text)
        self.assertNotIn('$proxy_add_x_forwarded_for', text)
        self.assertNotIn('location /immich', text)

    def test_apply_requires_account_attestation_before_host_changes(self):
        with patch.object(sys, 'argv', ['immich-proxy', '--apply']), patch.object(proxy.runtime, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'owner login'):
                proxy.main()
            run.assert_not_called()

    def test_apply_requires_administrator_before_host_changes(self):
        with patch.object(sys, 'argv', ['immich-proxy', '--apply', '--accounts-ready']), \
                patch.object(proxy.os, 'geteuid', return_value=1000), patch.object(proxy.runtime, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Administrator access'):
                proxy.main()
            run.assert_not_called()
