from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
import navidrome


class NavidromeTests(unittest.TestCase):
    def setUp(self):
        self.password = None
        self.calls = []
        self.bad_login = False
        self.reject_token = False
        self.page = None
        test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, data):
                self.send_response(status)
                self.end_headers()
                self.wfile.write((data if isinstance(data, str) else json.dumps(data)).encode())

            def do_GET(self):
                test.calls.append(('GET', self.path))
                if self.path == '/app/':
                    config = json.dumps({'firstTime': test.password is None})
                    self.reply(200, test.page if test.page is not None else
                               '<script>window.__APP_CONFIG__ = ' + json.dumps(config) + '</script>')
                elif self.path == '/api/user/user-id':
                    if test.reject_token or self.headers.get('X-ND-Authorization') != 'Bearer private-token':
                        self.reply(401, {'error': 'private-token'})
                    else:
                        self.reply(200, {'id': 'user-id', 'userName': 'admin', 'isAdmin': True})
                else:
                    self.reply(404, {})

            def do_POST(self):
                test.calls.append(('POST', self.path))
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path == '/auth/createAdmin':
                    if test.password is not None:
                        self.reply(403, {})
                        return
                    test.password = data['password']
                elif self.path != '/auth/login':
                    self.reply(404, {})
                    return
                if data != {'username': 'admin', 'password': test.password}:
                    self.reply(401, {'error': data['password']})
                    return
                self.reply(200, {} if test.bad_login else {'id': 'user-id', 'username': 'admin',
                           'isAdmin': True, 'token': 'private-token'})

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = 'http://127.0.0.1:' + str(server.server_port)

    def test_bootstrap_and_rerun_prove_login_without_changing_password(self):
        navidrome.connect(self.url, 'supplied-secret')
        navidrome.connect(self.url, 'supplied-secret')
        self.assertEqual(self.password, 'supplied-secret')
        self.assertEqual(self.calls, [('GET', '/app/'), ('POST', '/auth/createAdmin'),
                         ('POST', '/auth/login'), ('GET', '/api/user/user-id'),
                         ('GET', '/app/'), ('POST', '/auth/login'), ('GET', '/api/user/user-id')])

    def test_wrong_existing_password_fails_without_reset_or_secret_error(self):
        self.password = 'existing-secret'
        with self.assertRaises(RuntimeError) as error:
            navidrome.connect(self.url, 'wrong-secret')
        self.assertNotIn('wrong-secret', str(error.exception))
        self.assertEqual(self.password, 'existing-secret')
        self.assertEqual(self.calls, [('GET', '/app/'), ('POST', '/auth/login')])

    def test_unknown_bootstrap_state_fails_without_mutation(self):
        for page in ['<html>proxy error</html>', 'window.__APP_CONFIG__ = {bad}',
                     'window.__APP_CONFIG__ = {"firstTime": "true"}']:
            self.page = page
            with self.assertRaisesRegex(RuntimeError, 'bootstrap state'):
                navidrome.connect(self.url, 'supplied-secret')
        self.assertIsNone(self.password)
        self.assertTrue(all(method == 'GET' for method, path in self.calls))

    def test_success_status_without_login_token_is_rejected(self):
        self.password = 'supplied-secret'
        self.bad_login = True
        with self.assertRaisesRegex(RuntimeError, 'login was not verified'):
            navidrome.connect(self.url, self.password)
        self.assertNotIn(('GET', '/api/user/user-id'), self.calls)

    def test_protected_api_rejecting_token_fails_closed(self):
        self.password = 'supplied-secret'
        self.reject_token = True
        with self.assertRaises(RuntimeError) as error:
            navidrome.connect(self.url, self.password)
        self.assertNotIn('private-token', str(error.exception))
        self.assertNotIn(('POST', '/auth/createAdmin'), self.calls)


if __name__ == '__main__':
    unittest.main()
