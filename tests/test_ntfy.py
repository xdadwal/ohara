import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import alerts
import config
import credentials
import ntfy
import ntfy_proxy
import credential_fixtures


class NtfyTests(unittest.TestCase):
    def test_config_does_not_return_optional_password(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'.env').write_text((ROOT/'.env.example').read_text()+'\nNTFY_PASSWORD=Disposable notification password $ # =\n')
            (root/'.env').chmod(0o600)
            values=config.load(root/'.env')
            self.assertNotIn('NTFY_PASSWORD',values)
            self.assertEqual(ntfy.password(root),'Disposable notification password $ # =')

    def test_main_credentials_ignore_ntfy_without_forwarding_it(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);credential_fixtures.write(root)
            with (root/'.env').open('a') as f:f.write('NTFY_PASSWORD=Disposable ntfy only password\n')
            hp,media=credentials.load(root)
            self.assertNotIn('NTFY_PASSWORD',hp);self.assertNotIn('NTFY_PASSWORD',media)

    def test_storage_overlap_and_unapproved_relay_refused(self):
        c=config.load(ROOT/'.env.example')
        for extra in [{'NTFY_ROOT':c['DATA_ROOT']},{'NTFY_ROOT':c['MEDIA_ROOT']+'/ntfy'},
                      {'NTFY_IOS_RELAY':'https://unknown.example'}, {'NTFY_HOST':c['HOMEPAGE_HOST']}]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):ntfy.settings(c|extra)

    def test_password_byte_limit_and_missing_password(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'.env';p.write_text('');p.chmod(0o600)
            with self.assertRaises(ValueError):ntfy.password(root)
            p.write_text('NTFY_PASSWORD='+'x'*73+'\n')
            with self.assertRaises(ValueError):ntfy.password(root)

    def test_prepare_hashes_only_given_password_and_preserves_existing_config(self):
        import bcrypt
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'ntfy'
            (root/'.env').write_text('NTFY_PASSWORD=Disposable notification password\n');(root/'.env').chmod(0o600)
            c=config.load(ROOT/'.env.example')|{'NTFY_ROOT':str(base),'RUN_UID':str(__import__('os').getuid()),'RUN_GID':str(__import__('os').getgid())}
            with patch.object(ntfy,'check'),patch.object(ntfy,'storage'):
                ntfy.prepare(c,root)
                p=base/'config/server.yml';before=p.read_bytes()
                cfg=json.loads(before)
                self.assertEqual(cfg['auth-default-access'],'deny-all')
                self.assertFalse(cfg['enable-signup']);self.assertNotIn('upstream-base-url',cfg)
                self.assertEqual(cfg['auth-access'],['admin:ohara-alerts:rw'])
                self.assertNotIn('Disposable notification password',p.read_text())
                self.assertTrue(bcrypt.checkpw(b'Disposable notification password',cfg['auth-users'][0].split(':')[1].encode()))
                ntfy.prepare(c,root);self.assertEqual(before,p.read_bytes())

    def test_status_requires_anonymous_denial_and_authenticated_access(self):
        cases=[([(200,b'{"healthy":true}'),(200,b''),(200,b'')],False),
               ([(200,b'{"healthy":true}'),(403,b''),(403,b''),(401,b'')],False),
               ([(200,b'{"healthy":true}'),(403,b''),(200,b'')],False),
               ([(200,b'{"healthy":true}'),(403,b''),(403,b''),(200,b'')],True)]
        for replies,good in cases:
            with patch.object(ntfy,'request',side_effect=replies):
                if good:ntfy.status({},ROOT)
                else:
                    with self.assertRaises(ValueError):ntfy.status({},ROOT)

    def test_proxy_streaming_and_edge_headers(self):
        c=config.load(ROOT/'.env.example');text=ntfy_proxy.render(c,ROOT)
        self.assertIn('proxy_buffering off;',text)
        self.assertIn('proxy_set_header X-Forwarded-For $remote_addr;',text)
        self.assertIn('proxy_set_header Upgrade $http_upgrade;',text)
        self.assertIn('return 308 https://$host$request_uri;',text)
        self.assertIn('127.0.0.1:2586',text)

    def test_proxy_refuses_activation_before_authentication(self):
        with patch.object(ntfy_proxy.os,'geteuid',return_value=0),patch.object(ntfy,'status',side_effect=ValueError('not ready')),patch.object(ntfy_proxy.bambuddy_proxy,'deploy') as deploy:
            with self.assertRaises(ValueError):ntfy_proxy.apply({'DOMAIN':'xdadwal.in'},ROOT)
            deploy.assert_not_called()


class AlertTests(unittest.TestCase):
    def test_initial_health_is_quiet_then_two_failures_alert_once(self):
        state={}
        alerts.observe(state,'a',True,'Jellyfin',now=0)
        alerts.observe(state,'a',False,'Jellyfin',now=1)
        self.assertFalse(state.get('outbox'))
        alerts.observe(state,'a',False,'Jellyfin',now=2)
        self.assertEqual(len(state['outbox']),1)
        alerts.observe(state,'a',False,'Jellyfin',now=3)
        self.assertEqual(len(state['outbox']),1)
        alerts.observe(state,'a',True,'Jellyfin',now=4)
        self.assertEqual(len(state['outbox']),2)
        self.assertEqual(state['outbox'][1]['priority'],'3')

    def test_drive_loss_is_immediate_and_short_service_flaps_are_quiet(self):
        state={}
        alerts.observe(state,'disk:a',False,'WD drive',threshold=1)
        self.assertEqual(len(state['outbox']),1)
        alerts.observe(state,'service',False,'Jellyfin')
        alerts.observe(state,'service',True,'Jellyfin')
        self.assertEqual(len(state['outbox']),1)

    def test_failed_delivery_retains_queue_without_duplicate_outage(self):
        c={'drives':[],'pool':None,'checks':[{'label':'Jellyfin','url':'http://127.0.0.1:8096/health','media':True}]}
        state={}
        with patch.object(alerts,'http_good',return_value=False),patch.object(alerts,'send',side_effect=OSError):
            alerts.tick(c,state);alerts.tick(c,state);alerts.tick(c,state)
        self.assertEqual(len(state['outbox']),1)
        with patch.object(alerts,'http_good',return_value=False),patch.object(alerts,'send') as send:
            alerts.tick(c,state);send.assert_called_once()
        self.assertFalse(state['outbox'])

    def test_pool_loss_suppresses_eight_secondary_service_alerts(self):
        c={'drives':[],'pool':'/ohara/mnt','checks':[{'label':'Jellyfin','url':'http://127.0.0.1:8096/health','media':True}]}
        state={}
        with patch.object(Path,'read_text',return_value=''),patch.object(alerts,'http_good') as health,patch.object(alerts,'send',side_effect=OSError):
            alerts.tick(c,state);alerts.tick(c,state)
        health.assert_not_called();self.assertEqual(len(state['outbox']),1)

    def test_state_save_is_atomic_and_private(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';alerts.save(p,{'checks':{}})
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(p.read_text()),{'checks':{}})
            self.assertFalse(p.with_suffix('.tmp').exists())

    def test_state_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';target=Path(d)/'target';target.write_text('preserve')
            p.symlink_to(target)
            with self.assertRaises(ValueError):alerts.save(p,{})
            self.assertEqual(target.read_text(),'preserve')


class AccountRotationTests(unittest.TestCase):
    def test_offline_rename_preserves_account_identity_and_related_state(self):
        import sqlite3
        db=sqlite3.connect(':memory:')
        try:
            db.executescript('''CREATE TABLE user(id TEXT,user TEXT,pass TEXT,role TEXT,provisioned INT,prefs TEXT);
              CREATE TABLE user_access(user_id TEXT,topic TEXT);
              CREATE TABLE user_token(user_id TEXT,token TEXT);
              INSERT INTO user VALUES('same-id','ohara','dummy-hash','user',1,'preserved preferences');
              INSERT INTO user_access VALUES('same-id','ohara-alerts');
              INSERT INTO user_token VALUES('same-id','dummy-existing-token');''')
            self.assertEqual(ntfy.rename_database(db),('same-id','user'))
            self.assertEqual(db.execute('SELECT user,prefs FROM user').fetchone(),('admin','preserved preferences'))
            self.assertEqual(db.execute('SELECT user_id,topic FROM user_access').fetchone(),('same-id','ohara-alerts'))
            self.assertEqual(db.execute('SELECT user_id,token FROM user_token').fetchone(),('same-id','dummy-existing-token'))
            self.assertEqual(ntfy.rename_database(db),('same-id','user'))
        finally:db.close()

    def test_rename_refuses_colliding_accounts_without_modifying_them(self):
        import sqlite3
        db=sqlite3.connect(':memory:')
        try:
            db.executescript('''CREATE TABLE user(id TEXT,user TEXT,pass TEXT,role TEXT,provisioned INT);
              INSERT INTO user VALUES('old','ohara','dummy','user',1);
              INSERT INTO user VALUES('other','admin','dummy','user',0);''')
            with self.assertRaises(ValueError):ntfy.rename_database(db)
            self.assertEqual(db.execute('SELECT user FROM user ORDER BY id').fetchall(),[('ohara',),('admin',)])
        finally:db.close()

    def test_short_password_requires_explicit_exception_and_remains_nonempty(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'.env'
            p.write_text('NTFY_PASSWORD=weak\n');p.chmod(0o600)
            with self.assertRaises(ValueError):ntfy.password(root)
            p.write_text('NTFY_PASSWORD=weak\nNTFY_ALLOW_SHORT_PASSWORD=true\n')
            self.assertEqual(ntfy.password(root),'weak')
            p.write_text('NTFY_PASSWORD=\nNTFY_ALLOW_SHORT_PASSWORD=true\n')
            with self.assertRaises(ValueError):ntfy.password(root)
            p.write_text('NTFY_PASSWORD='+('x'*73)+'\nNTFY_ALLOW_SHORT_PASSWORD=true\n')
            with self.assertRaises(ValueError):ntfy.password(root)
