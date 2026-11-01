"""Deployment boundaries and account guards for the optional shortener."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import credentials
import kutt
import kutt_proxy


class KuttTests(unittest.TestCase):
    def setUp(self):self.c=config.load(ROOT/'.env.example')

    def test_storage_and_hostname_overlap_refused(self):
        self.assertEqual(kutt.settings(self.c)[0],'kutt.xdadwal.in')
        for changes in ({'KUTT_ROOT':self.c['MEDIA_ROOT']+'/kutt'},{'KUTT_ROOT':self.c['DATA_ROOT']+'/immich/kutt'},{'KUTT_ROOT':'/tmp/../etc/kutt'},{'KUTT_HOST':self.c['HOMEPAGE_HOST']},{'KUTT_HOST':'radarr.xdadwal.in'},{'RUN_UID':'0'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):kutt.settings(self.c | changes)

    def test_private_inputs_are_narrow_literal_and_not_shared(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'.env'
            p.write_text("KUTT_DB_PASSWORD=Fixture DB ' $ # = password\nKUTT_JWT_SECRET=Fixture signing 0123456789abcdef0123456789\nKUTT_PASSWORD=Fixture owner password\n")
            p.chmod(0o600)
            self.assertIn("' $ # =",kutt.secrets(root)['KUTT_DB_PASSWORD'])
            self.assertNotIn('KUTT_PASSWORD',kutt.secrets(root))
            self.assertEqual(kutt.owner_password(root),'Fixture owner password')
            p.write_text('KUTT_DB_PASSWORD=  Fixture database secret\nKUTT_JWT_SECRET=Fixture signing 0123456789abcdef0123456789\n')
            with self.assertRaises(ValueError):kutt.secrets(root)
            p.chmod(0o644)
            with self.assertRaises(ValueError):kutt.secrets(root)

    def test_model_exposure_and_policy_validation(self):
        model=json.loads(kutt.compose(self.c,ROOT,['config','--format','json'],capture=True))
        kutt.validate_model(model,self.c,ROOT)
        cases=[]
        bad=copy.deepcopy(model);bad['services']['postgres']['ports']=[{'target':5432,'published':'5432'}];cases.append(bad)
        bad=copy.deepcopy(model);bad['services']['kutt']['environment']['DISALLOW_ANONYMOUS_LINKS']='false';cases.append(bad)
        bad=copy.deepcopy(model);bad['services']['kutt']['user']='0:0';cases.append(bad)
        bad=copy.deepcopy(model);bad['services']['kutt']['volumes'][0]['source']='/var/run/docker.sock';cases.append(bad)
        for bad in cases:
            with self.assertRaises(ValueError):kutt.validate_model(bad,self.c,ROOT)

    def test_proxy_has_independent_source_guards_and_no_redirect_cache(self):
        c=self.c | {'KUTT_LAN_NETWORK':'192.168.1.0/24'}
        onboarding=kutt_proxy.render(c,ROOT)
        public=kutt_proxy.render(c,ROOT,public=True)
        self.assertEqual(onboarding.count('if ($ohara_kutt_allowed = 0)'),3)
        self.assertEqual(public.count('if ($ohara_kutt_allowed = 0)'),1)
        self.assertIn('proxy_set_header X-Forwarded-For $remote_addr;',public)
        self.assertIn('proxy_cache off;',public)
        self.assertIn('Cache-Control "no-store" always;',public)
        self.assertIn('auth/create-admin',public)
        with self.assertRaises(ValueError):kutt_proxy.network(c | {'KUTT_LAN_NETWORK':'0.0.0.0/0'})
        with self.assertRaises(ValueError):kutt_proxy.tls_paths(c | {'DOMAIN':'example.org'})

    def test_public_activation_requires_native_owner_login(self):
        c=self.c | {'KUTT_LAN_NETWORK':'192.168.1.0/24'}
        with patch.object(kutt_proxy.os,'geteuid',return_value=0),patch.object(kutt,'status'),patch.object(kutt,'require_accounts',side_effect=ValueError('owner pending')),patch.object(kutt_proxy.bambuddy_proxy,'deploy') as deploy:
            with self.assertRaises(ValueError):kutt_proxy.apply(c,ROOT,public=True)
        deploy.assert_not_called()

    def test_ambiguous_existing_accounts_do_not_get_reset(self):
        with patch.object(kutt,'owner_password',return_value='Fixture owner password'),patch.object(kutt,'sql',return_value='one@example.test\ntwo@example.test'),patch.object(kutt,'client') as client:
            with self.assertRaises(ValueError):kutt.require_accounts(self.c,ROOT)
        client.assert_not_called()

    def test_restore_keeps_private_sql_off_argv_and_checks_inputs(self):
        fixture='-- private fixture SQL\nSELECT 1;'
        with patch.object(kutt,'check') as check,patch.object(kutt,'compose') as compose:
            kutt.restore_sql(self.c,ROOT,fixture)
        check.assert_called_once_with(self.c,ROOT)
        self.assertEqual(compose.call_args.kwargs['input'],fixture)
        self.assertNotIn(fixture,compose.call_args.args[2])

    def test_startup_needs_only_db_and_jwt_and_verification_prompt_is_transient(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'.env'
            original='KUTT_DB_PASSWORD=Fixture database password\nKUTT_JWT_SECRET=Fixture signing 0123456789abcdef0123456789\n'
            p.write_text(original);p.chmod(0o600)
            self.assertEqual(set(kutt.secrets(root)),{'KUTT_DB_PASSWORD','KUTT_JWT_SECRET'})
            with patch.object(kutt.sys.stdin,'isatty',return_value=True),patch.object(kutt.getpass,'getpass',return_value='Fixture temporary owner'):
                self.assertEqual(kutt.owner_password(root),'Fixture temporary owner')
            self.assertEqual(p.read_text(),original)
            with patch.object(kutt.sys.stdin,'isatty',return_value=False),patch.object(kutt.getpass,'getpass') as prompt:
                with self.assertRaises(ValueError):kutt.owner_password(root)
            prompt.assert_not_called()
