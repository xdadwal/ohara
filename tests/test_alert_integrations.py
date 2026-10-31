"""Fault fixtures exercise transitions without stopping live services or printing."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lib'))
import alerts


class IntegrationTests(unittest.TestCase):
    def test_printer_completion_pause_errors_and_initial_baseline(self):
        s={};r={'id':1,'connected':True,'state':'FINISH','hms_errors':[]}
        alerts.printer_events(s,r)
        self.assertFalse(s.get('outbox'))
        for value in ('RUNNING','PAUSE','PAUSE','RUNNING','FINISH'):
            r['state']=value;alerts.printer_events(s,r)
        self.assertEqual([m['title'] for m in s['outbox']],['Ohara: printer pause','Ohara: printer finish'])
        r['connected']=False
        alerts.printer_events(s,r);alerts.printer_events(s,r)
        self.assertEqual(len(s['outbox']),3)
        r['connected']=True;alerts.printer_events(s,r)
        self.assertEqual(len(s['outbox']),4)

    def test_container_crash_loop_oom_and_recreation_baseline(self):
        s={};r={'project':'ohara','service':'jellyfin','media':True}
        info={'Id':'a','RestartCount':0,'State':{'Running':True,'OOMKilled':False}}
        alerts.container_events(s,r,info)
        info['RestartCount']=3;info['State']['OOMKilled']=True
        alerts.container_events(s,r,info);alerts.container_events(s,r,info)
        self.assertEqual(len(s['outbox']),2)
        info['Id']='b';info['RestartCount']=100
        alerts.container_events(s,r,info)
        self.assertEqual(len(s['outbox']),3)  # replacement clears the old crash loop
        info['State']['Running']=False
        alerts.container_events(s,r,info);alerts.container_events(s,r,info)
        self.assertEqual(len(s['outbox']),4)

    def test_pool_failure_suppresses_container_probes(self):
        c={'integrations':{'containers':[{'project':'ohara','service':'jellyfin','media':True}]}}
        with patch.object(alerts,'command') as cmd:
            alerts.extra_checks(c,{},False)
        cmd.assert_not_called()

    def test_watchdog_five_minute_backoff_is_not_exhaustion(self):
        s={};c={'integrations':{'watchdog':True}}
        with patch.object(alerts.Path,'read_text',return_value=json.dumps({'last_action':'cooldown','attempts':[99]})),patch.object(alerts.time,'monotonic',return_value=100),patch.object(alerts,'command',return_value='active'):
            alerts.extra_checks(c,s,True)
        self.assertFalse(s.get('outbox'))
        with patch.object(alerts.Path,'read_text',return_value=json.dumps({'last_action':'cooldown','attempts':[97,98,99]})),patch.object(alerts.time,'monotonic',return_value=100),patch.object(alerts,'command',return_value='active'):
            alerts.extra_checks(c,s,True)
        self.assertEqual(len(s['outbox']),1)
        with patch.object(alerts.Path,'read_text',return_value=json.dumps({'last_action':'healthy'})),patch.object(alerts,'command',return_value='active'):
            alerts.extra_checks(c,s,True);alerts.extra_checks(c,s,True)
        self.assertEqual(sum('storage recovered' in m['title'] for m in s['outbox']),1)

    def test_invalid_targets_are_rejected(self):
        for c in ({'tls':['host;touch /tmp/bad']},{'containers':[{'project':'--help','service':'x','media':True}]},{'dns':'8.8.8.8'},{'other':True}):
            with self.subTest(c=c),self.assertRaises(ValueError):alerts.validate_integrations(c)

    def test_seerr_changes_only_native_provider_and_keeps_existing_event_bits(self):
        import media
        import ntfy
        import credentials
        before={'enabled':True,'types':16,'options':{'url':'https://ntfy.example.org','topic':'ohara-alerts'}}
        saved=[]
        class API:
            def call(self,path,body=None):
                if path.endswith('/test'):return {'success':True}
                if body is not None:saved.append(body);return body
                return saved[-1] if saved else before
        with patch.object(alerts.os,'geteuid',return_value=0),patch.object(ntfy,'status'),patch.object(ntfy,'settings',return_value=('ntfy.example.org',)),patch.object(ntfy,'password',return_value='private-input'),patch.object(credentials,'load',return_value=({'HOMEPAGE_VAR_SEERR_API_KEY':'supplied-key'},{})),patch.object(media,'Client',return_value=API()),patch.object(alerts,'save'):
            alerts.seerr({},Path('/unused'))
        self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]['types'],2|16|128|4096)
        self.assertFalse(saved[0]['embedPoster'])

    def test_docker_cli_uses_private_runtime_config_without_unhiding_home(self):
        unit=(Path(__file__).resolve().parents[1]/'configs/systemd/ohara-alerts.service').read_text()
        self.assertIn('ProtectHome=yes',unit)
        self.assertIn('RuntimeDirectory=ohara-alerts-docker',unit)
        self.assertIn('RuntimeDirectoryMode=0700',unit)
        self.assertIn('Environment=DOCKER_CONFIG=/run/ohara-alerts-docker',unit)
